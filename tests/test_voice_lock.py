"""One voice for the whole script (vt/voice_lock.py): cast once, the same level, every take checked."""
import numpy as np
import pytest
import soundfile as sf

from vt import paths, tts
from vt import voice_lock as VL


def voice(f0: float, seconds: float = 1.6, sr: int = tts.SR, loud: float = 0.3, bright: float = 0.5) -> np.ndarray:
    """A crude voiced sound: a harmonic series on `f0` with a syllable-rate swell, so pitch and spectral shape can be measured like speech."""
    t = np.arange(int(sr * seconds)) / sr
    x = sum((bright ** k) * np.sin(2 * np.pi * f0 * (k + 1) * t) for k in range(12))
    x = x * (0.55 + 0.45 * np.sin(2 * np.pi * 3.5 * t) ** 2)
    return (loud * x / np.abs(x).max()).astype("float32")


def test_the_reference_is_the_scripts_own_opening_in_whole_sentences():
    s = ["One short line.", "A second line that is a little longer than the first one.", "A third line keeps going and going until there is enough voice to hold.", "Never this."]
    text = VL.anchor_text(s)
    assert text.startswith("One short line.") and text.endswith("enough voice to hold.") and "Never" not in text
    assert len(VL.anchor_text(["x" * 900])) == VL.ANCHOR_MAX_CHARS


def test_every_sentence_is_brought_to_the_same_speech_level():
    quiet, loud = VL.level(voice(150, loud=0.08), tts.SR), VL.level(voice(150, loud=0.6), tts.SR)
    assert abs(VL.speech_db(quiet, tts.SR) - VL.speech_db(loud, tts.SR)) < 0.5
    hiss = (1e-5 * np.ones(tts.SR)).astype("float32")
    assert VL.speech_db(VL.level(hiss, tts.SR), tts.SR) < VL.SPEECH_DB - 30, "a near-silent take is never lifted into noise"


def test_a_take_that_sounds_like_another_person_is_found_and_a_steady_voice_is_not():
    same = [VL.signature(voice(140 + d), tts.SR) for d in (0, 2, -3, 1, 4, -2)]
    assert VL.outliers(same, None) == []
    other = same[:3] + [VL.signature(voice(230, bright=0.8), tts.SR)] + same[3:]
    assert VL.outliers(other, None) == [3]
    assert VL.outliers([None, None], None) == [], "takes too short to judge are never re-spoken"


def test_a_designed_voice_is_cast_once_and_every_sentence_is_cloned_from_it(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "omnivoice")
    cast, said = [], []

    def design(text, vid, rate, out, language="en", **k):                       # the anchor: spoken once from the description
        cast.append(text)
        sf.write(str(out), voice(140, seconds=3.0), tts.SR)

    def sentence(engine, vid, text, rate, out, instruction="", language="en", **lock):
        said.append((text, lock))
        sf.write(str(out), voice(140), tts.SR)

    monkeypatch.setattr(tts, "_synth_comfyvoice", design)
    monkeypatch.setattr(tts, "synth_sentence", sentence)
    script = "The first thing to know is simple. The second is harder to hear. The third ties them together."
    out = tts.synthesize(script, tmp_path / "a.wav", engine="comfyvoice", voice="design:A calm woman", language="en")
    assert len(cast) == 1 and cast[0].startswith("The first thing")
    anchors = {id(lock["anchor"]) for _, lock in said}
    assert len(said) == 3 and len(anchors) == 1, "every sentence is cloned from the one reference"
    assert {lock["direct"] for _, lock in said} == {False}, "a plain script never switches to the directed workflow"
    assert out["steadiness"]["respoken"] == [] and out["steadiness"]["locked"] == ["design:A calm woman"]
    tts.synthesize(script, tmp_path / "b.wav", engine="comfyvoice", voice="design:A calm woman", language="en")
    assert len(cast) == 1, "the reference is cached: casting twice costs nothing"


def test_one_directed_sentence_makes_the_whole_script_directed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "breeze")
    monkeypatch.setattr(tts, "_synth_comfyvoice", lambda text, vid, rate, out, **k: sf.write(str(out), voice(140, seconds=3.0), tts.SR))
    said = []

    def sentence(engine, vid, text, rate, out, instruction="", language="en", **lock):
        said.append((round(rate, 3), instruction, lock["direct"]))
        sf.write(str(out), voice(140), tts.SR)

    monkeypatch.setattr(tts, "synth_sentence", sentence)
    tts.synthesize("{slowly, very seriously} Never do this. Do this instead.", tmp_path / "a.wav", engine="comfyvoice", voice="design:A deep man", language="en")
    assert [d for _, _, d in said] == [True, True]
    assert said[0][1] == "slowly, very seriously" and said[1][1] == ""


def test_a_pace_note_moves_one_sentence_only_a_little(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "none")
    rates = []

    def sentence(engine, vid, text, rate, out, instruction=""):
        rates.append(round(rate, 3))
        sf.write(str(out), voice(140), tts.SR)

    monkeypatch.setattr(tts, "synth_sentence", sentence)
    tts.synthesize("{very slowly} One. Two.", tmp_path / "a.wav", engine="edge", voice="en-US-AriaNeural", rate=1.0, language="en")
    assert rates == [1 - tts.RATE_SWING, 1.0]


def test_a_sentence_in_another_voice_is_spoken_again_with_another_seed(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "none")
    calls = []

    def sentence(engine, vid, text, rate, out, instruction="", **lock):
        seed = lock.get("seed", tts.VOICE_SEED)
        calls.append((text, seed))
        drifted = text.startswith("Four") and seed == tts.VOICE_SEED                   # the first take of sentence four comes out as somebody else
        sf.write(str(out), voice(240, bright=0.8) if drifted else voice(140 + len(calls) % 3), tts.SR)

    monkeypatch.setattr(tts, "synth_sentence", sentence)
    script = "One is here now. Two is here now. Three is here now. Four is here now. Five is here now. Six is here now."
    out = tts.synthesize(script, tmp_path / "a.wav", engine="voicestudio", voice="kittentts:v", language="en")
    st = out["steadiness"]
    assert st["respoken"] == [3] and st["still_off"] == []
    assert [s for t, s in calls if t.startswith("Four")] == [tts.VOICE_SEED, tts.VOICE_SEED + 100]
    assert max(x for x in st["scores"] if x is not None) <= 1.0


def test_a_voice_that_cannot_be_cast_still_speaks_and_says_why(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "omnivoice")

    def broken(*a, **k):
        raise tts.TTSError("no server")

    monkeypatch.setattr(tts, "_synth_comfyvoice", broken)
    monkeypatch.setattr(tts, "synth_sentence", lambda engine, vid, text, rate, out, instruction="", **k: sf.write(str(out), voice(140), tts.SR))
    out = tts.synthesize("Hello there, friend. Goodbye now.", tmp_path / "a.wav", engine="comfyvoice", voice="design:x", language="en")
    assert out["duration"] > 2 and "no server" in out["steadiness"]["not_locked"][0]


def test_the_comfy_engine_clones_from_the_reference_when_a_clone_model_is_installed(monkeypatch, tmp_path):
    import vt.comfy as C
    import vt.comfy.voice as CV

    anchor = VL.Anchor(path=tmp_path / "ref.wav", text="The reference.", key="k")
    sf.write(str(anchor.path), voice(140), tts.SR)
    got = {}
    monkeypatch.setattr(tts, "_comfy_voice_servers", lambda: {"omnivoice_design": "http://x", "omnivoice_clone": "http://x"})
    monkeypatch.setattr(C, "ComfyClient", lambda url: type("C", (), {"close": lambda self: None})())
    monkeypatch.setattr(CV, "speak", lambda client, wf, text, out, **k: (got.update(wf=wf.id, **k), sf.write(str(out), voice(140), tts.SR)))
    tts._synth_comfyvoice("Hello.", "design:A calm woman", 1.0, tmp_path / "o.wav", language="bn", anchor=anchor, direct=False)
    assert got["wf"] == "omnivoice_clone" and got["ref_audio"] == anchor.path and got["ref_text"] == "The reference." and got["seed"] == tts.VOICE_SEED
    monkeypatch.setattr(tts, "_comfy_voice_servers", lambda: {"omnivoice_design": "http://x"})
    tts._synth_comfyvoice("Hello.", "design:A calm woman", 1.0, tmp_path / "o.wav", language="bn", anchor=anchor, direct=False)
    assert got["wf"] == "omnivoice_design", "without a clone model the designed voice is still spoken"
