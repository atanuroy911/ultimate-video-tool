"""Renders a photo as a scene backdrop and measures the contrast of the real pixels: the scrim chosen by the contrast engine must
deliver what it promised, using what the renderer actually draws (gradient stops, Ken Burns zoom and all)."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytestmark = pytest.mark.slow
TOLERANCE = 0.35        # the camera zoom moves the photo a little, so the measured ratio may differ slightly from the analysed one


def busy_photo(path: Path, kind: str):
    h, w = 1200, 900
    ys, xs = np.mgrid[0:h, 0:w]
    if kind == "checker":
        a = (((ys // 24 + xs // 24) % 2) * 255).astype("uint8")
        img = np.stack([a, a, a], axis=-1)
    elif kind == "bright":
        img = np.clip(235 + np.random.default_rng(1).normal(0, 12, (h, w, 3)), 0, 255).astype("uint8")
    else:
        img = np.clip(128 + np.random.default_rng(2).normal(0, 80, (h, w, 3)), 0, 255).astype("uint8")
    Image.fromarray(img).save(path)


def measured_ratio(frame: Path, ink: str, aspect: str) -> float:
    from vt.director import contrast as K
    im = np.asarray(Image.open(frame).convert("RGB")).astype("float64")
    zt, zb = K.zone(aspect)
    h = im.shape[0]
    return K.worst_ratio(K.luminance(im[int(zt * h): int(zb * h)]), 1.0 if ink == "light" else 0.0)


@pytest.fixture(scope="module")
def chrome_ok():
    from vt.render.hyperframes import BIN
    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")


@pytest.mark.parametrize("kind", ["checker", "bright", "noisy"])
@pytest.mark.parametrize("aspect", ["9:16", "1:1", "16:9"])
def test_rendered_backdrop_meets_the_promised_contrast(tmp_path, chrome_ok, kind, aspect):
    from vt.compose.composer import resolve_composition, write_composition
    from vt.director import contrast as K
    from vt.project import load_theme
    from vt.render.hyperframes import snapshot
    from vt.schema import Beat, Beats, ScenesFile, Transcript, Word

    photo = tmp_path / "photo.png"
    busy_photo(photo, kind)
    arr = np.asarray(Image.open(photo).convert("RGB"))
    scrim = K.decide([K.cover_crop(arr, aspect, 0.5, 0.5)], aspect)
    words = [Word(id=f"w{i}", text=f"w{i}", start=0.3 + i * 0.4, end=0.6 + i * 0.4) for i in range(1, 8)]
    beats = Beats(beats=[Beat(id="b1", word_ids=[w.id for w in words], start=0.3, end=3.0, text="x")])
    sf = ScenesFile.model_validate({"scenes": [{"id": "s1", "beats": ["b1"], "layout": "lower", "elements": [],
                                                "backdrop": {"media": "photo", "motion": "none", "scrim": scrim.model_dump()}}]})
    theme = load_theme("paper")
    media = {"photo": {"src": "media/photo.png", "kind": "image", "fx": 0.5, "fy": 0.5, "w": 900, "h": 1200, "trim": 0, "loop": False, "_abs": str(photo)}}
    data = resolve_composition(sf, Transcript(words=words), beats, theme, aspect, 4.0, None, media=media)
    data["captions"] = []                                   # only the backdrop and its scrim are measured
    idx = write_composition(tmp_path / "comp", data, theme)
    frame = snapshot(idx.parent, tmp_path / "snap", [2.0], gpu=False)[0]
    got = measured_ratio(frame, scrim.ink, aspect)
    assert got >= K.TARGET - TOLERANCE, f"{kind} {aspect}: promised {scrim.ratio}, measured {got:.2f} with {scrim}"
    # and the decision was not wasteful: the unfiltered photo really did need help (or none was applied)
    raw = max(measured_ratio(photo_frame, i, aspect) for i in ("light", "dark")) if (photo_frame := _raw_frame(arr, aspect, tmp_path)) else 99
    assert scrim.kind == "none" or raw < K.TARGET


def _raw_frame(arr, aspect, tmp_path):
    from vt.director import contrast as K
    crop = K.cover_crop(arr, aspect, 0.5, 0.5)
    out = tmp_path / "raw.png"
    Image.fromarray(crop).resize((1080, 1920) if aspect == "9:16" else (1920, 1080)).save(out)
    return out
