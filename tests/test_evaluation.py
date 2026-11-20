"""Automated visual evaluation of the director (plan P2-G): for every use case, in English and Bangla, plan a video from text, render a frame of
every scene with the real renderer, and check the things a person would complain about: an empty screen, content cut off at the edge, the same
look over and over, text that cannot be read."""
from collections import Counter

import numpy as np
import pytest
from PIL import Image

from test_director import BN_STORY, EDU, PRODUCT, STORY, make
from test_phase2_render import foreground_mask, stage_region

pytestmark = [pytest.mark.slow, pytest.mark.browser]

BN_PRODUCT = ["ধীর ভিডিও এডিটিংয়ে ক্লান্ত?", "পরিচয় করিয়ে দিই ভিডিওপ্রো, সবচেয়ে দ্রুত ভিডিও মেকার।", "এতে আছে টেমপ্লেট, অটো ক্যাপশন আর মিউজিক।",
              "১০০০০ এর বেশি গ্রাহক এটা ব্যবহার করেন।", "মাত্র ৫০০ টাকায় আজই অর্ডার করুন।"]
BN_EDU = ["মুদ্রাস্ফীতি কী?", "মুদ্রাস্ফীতি মানে জিনিসের দাম সময়ের সাথে বাড়ে।", "প্রথমে দাম বাড়ে। তারপর টাকার মূল্য কমে।", "আপনার কী করা উচিত?"]
CASES = [("product", PRODUCT, "en"), ("education", EDU, "en"), ("story", STORY, "en"), ("discussion", EDU, "en"),
         ("story", BN_STORY, "bn"), ("product", BN_PRODUCT, "bn"), ("education", BN_EDU, "bn")]


@pytest.fixture(scope="module")
def chrome_ok():
    from vt.render.hyperframes import BIN
    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")


def render_plan(tmp_path, usecase, texts, lang, aspect):
    from vt.compose.composer import resolve_composition, write_composition
    from vt.director import plan as D
    from vt.project import load_theme
    from vt.render.hyperframes import snapshot
    tr, beats = make(texts, wps=0.4)
    sf = D.plan(tr, beats, usecase=usecase, language=lang, seed=f"eval-{usecase}-{lang}", theme="minimal", aspect=aspect)
    theme = load_theme("minimal")
    dur = beats.beats[-1].end + 1.0
    data = resolve_composition(sf, tr, beats, theme, aspect, dur, None, language=lang)
    idx = write_composition(tmp_path / "comp", data, theme)
    times = [round(s["start"] + min(3.2, 0.75 * (s["end"] - s["start"])), 2) for s in data["scenes"]]
    return sf, snapshot(idx.parent, tmp_path / "snap", times), data


@pytest.mark.parametrize("aspect", ["9:16", "1:1", "16:9"])
@pytest.mark.parametrize("usecase,texts,lang", CASES, ids=[f"{u}-{l}" for u, _, l in CASES])
def test_planned_videos_have_no_empty_screens_and_nothing_is_cut_off(tmp_path, chrome_ok, usecase, texts, lang, aspect):
    sf, frames, data = render_plan(tmp_path, usecase, texts, lang, aspect)
    assert len(frames) == len(sf.scenes)
    for sc, f in zip(sf.scenes, frames):
        reg = stage_region(np.asarray(Image.open(f).convert("RGB")), aspect)
        m = foreground_mask(reg)
        assert m.mean() > 0.01, f"{usecase}/{lang} {aspect} scene {sc.id} ({sc.archetype}) is empty"
        side = max(m[:, :10].mean(), m[:, -10:].mean())
        assert side < 0.03 and m[:4].mean() < 0.03, f"{usecase}/{lang} {aspect} scene {sc.id} ({sc.archetype}) touches the frame edge"


def test_the_same_look_is_not_repeated_and_every_kind_uses_its_own_scenes():
    from vt.director import plan as D
    long_text = PRODUCT + EDU + STORY
    tr, beats = make(long_text, wps=0.4)
    for uc in ("product", "education", "story", "general"):
        sf = D.plan(tr, beats, usecase=uc, language="en", seed="rep", theme="paper")
        kinds = [s.archetype for s in sf.scenes]
        consecutive = sum(1 for a, b in zip(kinds, kinds[1:]) if a == b and a != "picture")   # picture scenes differ in content and pattern
        assert consecutive <= max(2, len(kinds) // 6), (uc, kinds)
        per_minute = len(set(kinds)) / max(1.0, beats.beats[-1].end / 60)
        assert per_minute >= 2.5 or len(set(kinds)) >= 5, (uc, kinds)   # junk infographics are refused now (phrases.tidy), so a little less variety
    prof = {uc: Counter(s.archetype for s in D.plan(tr, beats, usecase=uc, language="en", seed="rep").scenes) for uc in ("product", "story", "education")}
    assert prof["story"]["cartoon"] > prof["product"]["cartoon"] and prof["product"].keys() != prof["story"].keys()


def test_text_over_pictures_is_always_readable_in_planned_scenes(tmp_path):
    """Every planned backdrop carries a scrim whose promised contrast meets AA (the rendered-pixel check is in test_backdrop_render)."""
    from vt.director import media as M
    from vt.director import plan as D
    from vt.director.contrast import decide_for_media
    from vt.project import Project
    import soundfile as sf_
    sf_.write(str(tmp_path / "a.wav"), np.zeros(1600, dtype="float32"), 16000)
    import vt.paths as paths
    old = paths.PROJECTS
    paths.PROJECTS = tmp_path / "projects"
    try:
        proj = Project.create("e", tmp_path / "a.wav")
        rng = np.random.default_rng(4)
        items = []
        for i in range(4):
            img = np.clip(rng.integers(0, 256, (1, 1, 3)) + rng.normal(0, 60 + 30 * i, (480, 360, 3)), 0, 255).astype("uint8")
            Image.fromarray(img).save(tmp_path / f"p{i}.png")
            items.append(M.add_media(proj, tmp_path / f"p{i}.png", caption=f"photo {i}"))
        tr, beats = make(PRODUCT, wps=0.4)
        plan = D.plan(tr, beats, usecase="product", language="en", seed="r", media=items, scrim_fn=lambda m, a, l, t0, t1: decide_for_media(proj, m, a, l, t0, t1))
        bds = [s.backdrop for s in plan.scenes if s.backdrop]
        assert bds and all(b.scrim.ratio >= 4.5 or b.scrim.strength >= 0.9 for b in bds)
    finally:
        paths.PROJECTS = old
