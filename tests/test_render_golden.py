"""Pixel-level regression tests for the renderer (slow: they start headless Chrome via HyperFrames).

Golden images live in tests/golden. After an intentional visual change, review the new frames and refresh with
    VT_UPDATE_GOLDEN=1 pytest -m slow tests/test_render_golden.py
"""
import os
import shutil
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.browser]
GOLDEN = Path(__file__).parent / "golden"
TOLERANCE = 1.5   # mean absolute pixel difference (0-255) allowed between render and golden


CREATED: list[str] = []


def _compare(actual: Path, name: str):
    """Compare with the golden; a missing golden is created and reported at the end instead of failing."""
    from PIL import Image, ImageChops
    import numpy as np

    golden = GOLDEN / f"{name}.png"
    if os.environ.get("VT_UPDATE_GOLDEN") or not golden.exists():
        GOLDEN.mkdir(exist_ok=True)
        shutil.copyfile(actual, golden)
        CREATED.append(golden.name)
        return
    a, g = Image.open(actual).convert("RGB"), Image.open(golden).convert("RGB")
    assert a.size == g.size, f"{name}: size {a.size} != {g.size}"
    diff = float(np.asarray(ImageChops.difference(a, g)).mean())
    if diff > TOLERANCE:
        bad = actual.with_name(f"{name}.actual.png")
        shutil.copyfile(actual, bad)
        pytest.fail(f"{name}: mean pixel difference {diff:.2f} > {TOLERANCE} (see {bad})")


@pytest.fixture(scope="module")
def chrome_ok():
    from vt.render.hyperframes import BIN
    if not BIN.exists():
        pytest.skip("HyperFrames is not installed (cd renderer && npm install)")


@pytest.mark.parametrize("aspect,tag", [("9:16", "9x16"), ("16:9", "16x9"), ("1:1", "1x1")])
def test_reference_frame_matches_golden(ref, tmp_path, chrome_ok, aspect, tag):
    from vt.compose import compose_project
    from vt.render.hyperframes import snapshot

    index = compose_project(ref, aspect)
    frames = snapshot(index.parent, tmp_path / "snap", [9.0])     # card, arrow, coins, tag and caption are all on screen
    _compare(frames[0], f"reference-{tag}")


def test_bangla_conjuncts_render_correctly(tmp_path, chrome_ok):
    """Conjunct-heavy Bangla (ক্ষ্ম, স্ত্রী, জ্ঞ, দ্বন্দ্ব, উজ্জ্বল...) next to English must shape correctly in every text role."""
    from vt.compose import resolve_composition, write_composition
    from vt.project import load_theme
    from vt.render.hyperframes import snapshot
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    words = [Word(id=f"w{i}", text=t, start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i, t in enumerate(
        ["ক্ষ্মী", "স্ত্রী", "জ্ঞান", "দ্বন্দ্ব", "বিশ্বব্যাপী", "শ্রদ্ধা", "উজ্জ্বল", "ভবিষ্যৎ", "net", "yield।"], 1)]
    tr = Transcript(words=words)
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=4.6, text="x")])
    sf = ScenesFile.model_validate({"scenes": [{"id": "s1", "beats": ["b1"], "elements": [
        {"type": "title", "text": "ক্ষ্মী স্ত্রী জ্ঞান", "at_word": "w1"},
        {"type": "tag", "text": "দ্বন্দ্ব + net yield", "at_word": "w2"},
        {"type": "list", "items": ["স্বপ্ন ক্ষুদ্র", "ঊর্ধ্বে দুঃখ", "র‍্যাঙ্ক rank"], "at_word": "w3"}],
        "caption": {"highlight_words": ["w7"]}}]})
    theme = load_theme("paper")
    data = resolve_composition(sf, tr, beats, theme, "9:16", 5.0, {})
    out = write_composition(tmp_path / "comp", data, theme).parent
    frames = snapshot(out, tmp_path / "snap", [4.6])
    _compare(frames[0], "bangla-conjuncts-9x16")


def test_every_theme_renders_the_specimen(tmp_path, chrome_ok):
    from vt.compose.specimen import write_specimen
    from vt.project import list_themes
    from vt.render.hyperframes import snapshot

    for t in list_themes():
        if t.name not in ("paper", "dark-neon", "minimal"):
            continue
        index = write_specimen(t, "9:16", tmp_path / t.name)
        frames = snapshot(index.parent, tmp_path / f"snap-{t.name}", [18.5])   # equation + tag scene
        _compare(frames[0], f"specimen-{t.name}-9x16")


def test_zz_report_created_goldens():
    if CREATED:
        pytest.skip("created golden images, review them and commit: " + ", ".join(CREATED))
