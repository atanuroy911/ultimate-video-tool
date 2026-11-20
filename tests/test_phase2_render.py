"""Every phase-2 element rendered by the real renderer in both shapes: it must be visible, stay inside the frame, and keep its look
(the contact sheets are pixel-compared with tests/golden after a visual review: VT_UPDATE_GOLDEN=1 pytest -m slow tests/test_phase2_render.py)."""
import numpy as np
import pytest
from PIL import Image

from test_render_golden import CREATED, _compare  # noqa: F401  (shared golden comparison)

pytestmark = [pytest.mark.slow, pytest.mark.browser]


@pytest.fixture(scope="module")
def chrome_ok():
    from vt.render.hyperframes import BIN
    if not BIN.exists():
        pytest.skip("HyperFrames is not installed")


@pytest.fixture(scope="module", params=["9:16", "1:1", "16:9"])
def shots(request, tmp_path_factory, chrome_ok):
    from vt.compose import showcase
    out = tmp_path_factory.mktemp("p2" + request.param.replace(":", "x"))
    frames = showcase.render(out, request.param, "minimal")
    return request.param, showcase.NAMES, frames, out


def stage_region(im: np.ndarray, aspect: str) -> np.ndarray:
    """The part of the frame where scene elements live (above the caption)."""
    h = im.shape[0]
    return im[: int(h * {"9:16": 0.72, "1:1": 0.74, "16:9": 0.74}[aspect])]


def foreground_mask(reg: np.ndarray) -> np.ndarray:
    corners = np.concatenate([reg[:12, :12].reshape(-1, 3), reg[:12, -12:].reshape(-1, 3), reg[-12:, :12].reshape(-1, 3), reg[-12:, -12:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)                      # the page colour, taken from the corners (an element may cover most of the frame)
    return np.abs(reg.astype("int16") - bg).sum(axis=2) > 36


def test_every_element_is_drawn(shots):
    aspect, names, frames, _ = shots
    assert len(frames) == len(names)
    for name, f in zip(names, frames):
        reg = stage_region(np.asarray(Image.open(f).convert("RGB")), aspect)
        covered = foreground_mask(reg).mean()
        assert covered > 0.012, f"{name} ({aspect}) is (almost) invisible: {covered:.4f}"


def test_nothing_is_cut_off_at_the_sides_or_top(shots):
    aspect, names, frames, _ = shots
    for name, f in zip(names, frames):
        reg = stage_region(np.asarray(Image.open(f).convert("RGB")), aspect)
        m = foreground_mask(reg)
        edge = 10
        side = max(m[:, :edge].mean(), m[:, -edge:].mean())
        top = m[:4].mean()
        assert side < 0.02 and top < 0.02, f"{name} ({aspect}) touches the frame edge (side {side:.3f}, top {top:.3f})"


def test_contact_sheet_matches_the_golden(shots):
    from vt.compose import showcase
    aspect, names, frames, out = shots
    tag = aspect.replace(":", "x")
    half = len(frames) // 2
    for part, sl in (("a", slice(0, half)), ("b", slice(half, None))):
        sheet = showcase.contact_sheet(frames[sl], aspect, out / f"sheet-{part}.png", cols=7 if aspect == "9:16" else 5 if aspect == "1:1" else 4)
        _compare(sheet, f"phase2-{tag}-{part}")
