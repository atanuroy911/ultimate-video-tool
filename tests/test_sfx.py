import json
import random

import numpy as np
import soundfile as sf

from vt import sfxlib
from vt.cues import build_cues
from vt.render import mux


def test_classification_by_filename_folder_and_weapon_priority():
    c = sfxlib.classify
    assert c("450 cinematic sound effects/Buttons/Button_01.wav")[0] == "click"
    assert c("336 SFX/WHOOSHES/Deep whoosh.wav")[0] == "whoosh"
    assert c("336 SFX/RISERS/01_RISER/Deep riser.wav")[0] == "riser"
    assert c("336 SFX/MIX/Apple Pay Success Sound Effect.mp3")[0] == "money"
    assert c("450 cinematic sound effects/Bells/Bells 01.wav")[0] == "chime"
    # a gun hidden in a generic folder is still a weapon, and weapons are never used automatically
    assert c("450 cinematic sound effects/Transition Sound Effects/9MM glock slide cock foley.mp3")[0] == "weapon"
    assert "weapon" in sfxlib.DISABLED_ROLES and "weapon" not in sfxlib.AUTO_ROLES
    assert c("some/folder/unknown thing.wav")[0] == "misc"


def test_franchise_and_explicit_files_are_flagged_but_ordinary_words_are_not():
    assert sfxlib.flag("230 mixed/one-piece-brooks-laugh.mp3")
    assert sfxlib.flag("memes/Wet_Fart_Meme.mp3") == "explicit/crude"
    assert sfxlib.flag("x/Discord Join.mp3")
    assert sfxlib.flag("450/mix/soundreality-ui-tuping-391160.mp3") is None   # 'tuping' must not match 'ipin'
    assert sfxlib.flag("x/peacock-call.mp3") is None and sfxlib.flag("x/essex-click.mp3") is None


def scenes():
    return [
        {"start": 0.0, "transition_in": "cut", "elements": [{"type": "title", "at": 0.3}]},
        {"start": 3.0, "transition_in": "slide_up", "elements": [{"type": "big_number", "at": 4.0}, {"type": "list", "at": 5.0, "items": ["a", "b", "c"]}]},
        {"start": 8.0, "transition_in": "zoom", "elements": [{"type": "icon_row", "at": 8.5, "count": 3}]},
    ]


def test_cues_have_roles_tiers_and_sensible_structure():
    cues = build_cues(scenes())
    roles = [(c["role"], c["tier"]) for c in cues]
    assert ("whoosh", 1) in roles and ("subdrop", 1) in roles and ("impact", 1) in roles
    assert any(c["role"] == "riser" and c["tier"] == 3 and abs(c["t"] - 2.6) < 0.01 for c in cues)   # riser 1.4 s before the big number
    assert [c["t"] for c in cues] == sorted(c["t"] for c in cues)
    list_clicks = [c for c in cues if c["role"] == "click"]
    assert len(list_clicks) == 3 and [c["tier"] for c in list_clicks] == [2, 3, 3]        # first row normal, the rest rich-only


def make_lib(root):
    (root / "lib" / "whoosh").mkdir(parents=True)
    clips = []
    for i in range(4):
        t = np.arange(4410) / 44100
        sf.write(str(root / "lib" / "whoosh" / f"w{i}.ogg"), (0.5 * np.sin(2 * np.pi * (300 + 150 * i) * t)).astype("float32"), 44100, format="OGG", subtype="VORBIS")
        clips.append({"id": f"whoosh-{i}", "role": "whoosh", "file": f"whoosh/w{i}.ogg", "duration": 0.1, "peak_db": -1, "centroid": 300, "source": "x", "tags": []})
    (root / "library.json").write_text(json.dumps({"clips": clips}), encoding="utf-8")


def test_picker_never_repeats_recent_clips_and_is_deterministic(tmp_path):
    make_lib(tmp_path)
    lib = sfxlib.Library(tmp_path)
    picks, rng = [], random.Random("seed")
    for _ in range(8):
        picks.append(lib.pick("whoosh", rng, avoid=set(picks[-3:])).id)
    assert all(a != b for a, b in zip(picks, picks[1:]))
    rng2, again = random.Random("seed"), []
    for _ in range(8):
        again.append(lib.pick("whoosh", rng2, avoid=set(again[-3:])).id)
    assert picks == again
    assert lib.pick("weapon", random.Random(0)) is None and lib.pick("nonexistent", random.Random(0)) is None


def test_mixer_levels_and_determinism(tmp_path):
    cues = build_cues(scenes())
    outs = {lvl: mux.build_sfx_track(cues, 12.0, tmp_path / f"{lvl}.wav", lvl, seed="p1") for lvl in ("off", "subtle", "normal", "rich")}
    assert outs["off"] is None
    counts = {}
    for lvl in ("subtle", "normal", "rich"):
        x, sr = sf.read(str(outs[lvl]))
        assert sr == 44100 and abs(len(x) / sr - 14.0) < 0.1 and np.abs(x).max() <= 1.0
        counts[lvl] = int((np.abs(x[:, 0]) > 1e-4).sum())
    assert counts["subtle"] < counts["normal"] < counts["rich"]       # more sound as the level rises
    again = mux.build_sfx_track(cues, 12.0, tmp_path / "again.wav", "normal", seed="p1")
    assert sf.read(str(again))[0].tobytes() == sf.read(str(outs["normal"]))[0].tobytes()   # same seed, same sounds


def test_old_boolean_sfx_option_still_switches_everything_off():
    from vt.schema import Options
    assert mux.sfx_level(Options(sfx=False)) == "off"
    assert mux.sfx_level(Options(sfx=True, sfx_level="rich")) == "rich"
    assert mux.sfx_level(Options()) == "normal"
