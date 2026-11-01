"""Stick-figure scenes: they compose with their timeline, and (slow) the real renderer draws a figure in every aspect."""
import numpy as np
import pytest
from PIL import Image

from vt.planner import plan_rules
from vt.script.rules_stick import rules_script
from vt.script import compile_script
from vt.pipeline import compose_all


def stick_project(ref):
    tr, beats = ref.transcript(), ref.beats()
    script = rules_script(tr, beats, plan_rules(tr, beats), kind="stick")
    ref.save_scenes(compile_script(script, tr, beats, ref.meta().theme))
    return ref


def test_composition_carries_the_stick_timeline(ref):
    import json

    stick_project(ref)
    compose_all(ref)
    data = json.loads((ref.comp_dir / "9x16" / "data.json").read_text(encoding="utf-8"))
    sc = data["scenes"][0]
    assert sc["archetype"] == "stick" and sc["layout"] == "upper"
    st = sc["stick"]
    assert st["set"]["kind"] and st["cast"] and st["actions"][0]["do"] in ("walk_in", "appear")
    assert all(a["start"] < a["end"] for a in st["actions"])
    assert (ref.comp_dir / "9x16" / "runtime" / "vt-stick.js").exists()


@pytest.mark.slow
@pytest.mark.parametrize("aspect", ["9:16", "1:1", "16:9"])
def test_figure_is_drawn_in_every_shape(ref, aspect, tmp_path):
    from vt.compose import FORMATS
    from vt.render.hyperframes import BIN, snapshot

    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")
    stick_project(ref)
    compose_all(ref)
    files = snapshot(ref.comp_dir / FORMATS[aspect]["tag"], tmp_path, [1.5])
    im = np.asarray(Image.open(files[0]).convert("RGB")).astype("int16")
    h, w = im.shape[:2]
    bg = np.median(im[:10, :10].reshape(-1, 3), axis=0)
    dark = (np.abs(im - bg).sum(axis=2) > 200)             # ink-coloured pixels: the figure, the set lines
    assert dark.mean() > 0.004, "no figure drawn"


def test_sound_cues_follow_stick_actions_and_script_sfx():
    from vt.cues import build_cues

    scene = {"start": 0.0, "transition_in": "cut", "elements": [], "sfx": [{"t": 1.0, "id": "ding"}],
             "stick": {"actions": [{"do": "jump", "start": 2.0, "end": 2.8}, {"do": "wave", "start": 4.0, "end": 5.0}]}}
    cues = build_cues([scene])
    assert {"t": 1.0, "role": "chime", "tier": 1} in cues
    assert any(c["role"] == "impact" and abs(c["t"] - 2.7) < 0.01 for c in cues)
    assert not any(abs(c["t"] - 4.0) < 0.01 for c in cues)             # a wave makes no sound
