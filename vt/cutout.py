"""Background removal for pictures: the main subject stays, the rest becomes transparent (a PNG with an alpha channel) so it can sit on a layer above other pictures or graphics.

The model is IS-Net "general use" (Apache 2.0, about 178 MB), the same one Concat and rembg use, run with ONNX Runtime. It is downloaded on first use into the models folder and
checked by size and SHA-256. Pictures only: a video would need a mask for every frame (not built).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

from . import paths

MODEL_FILE = "isnet-general-use.onnx"
MODEL_BYTES = 178648008
MODEL_SHA256 = "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
SIZE = 1024
_lock = threading.Lock()
_session = None


class CutoutError(RuntimeError):
    pass


def model_path() -> Path:
    return paths.MODELS / "cutout" / MODEL_FILE


def available() -> bool:
    import importlib.util                     # look, do not load: importing it here would load GPU libraries before torch's (vt/gpu.py)

    return importlib.util.find_spec("onnxruntime") is not None


def ready() -> bool:
    p = model_path()
    return p.exists() and p.stat().st_size == MODEL_BYTES


def ensure_model(progress: Optional[Callable[[float, str], None]] = None) -> Path:
    from . import models

    try:
        models.ensure("isnet-general-use", progress)
    except models.ModelError as e:
        raise CutoutError(f"The background-removal model has to be downloaded once (about 180 MB). Connect to the internet and try again. ({e})") from e
    return model_path()


def _load():
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort

            from . import gpu

            providers = gpu.onnx_providers()
            _session = ort.InferenceSession(str(ensure_model()), providers=providers)
    return _session


def matte(im: Image.Image) -> np.ndarray:
    """The subject's alpha (0-1, the picture's size)."""
    rgb = im.convert("RGB")
    small = np.asarray(rgb.resize((SIZE, SIZE), Image.BILINEAR), dtype="float32")
    small = small / max(float(small.max()), 1e-6)                    # the model was trained on pictures scaled by their own maximum
    x = ((small - 0.5) / 1.0).transpose(2, 0, 1)[None].astype("float32")
    sess = _load()
    y = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    y = (y - y.min()) / max(1e-6, float(y.max() - y.min()))
    a = Image.fromarray((y * 255).astype("uint8")).resize(rgb.size, Image.LANCZOS)
    return np.asarray(a, dtype="float32") / 255.0


def cut_out(src: Path, dst: Path) -> dict:
    """Write src with its background removed to dst (PNG). Returns how much of the picture is kept."""
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise CutoutError("this picture could not be opened") from e
    a = matte(im)
    # tidy the edge: a soft ramp instead of a hard 0.5 cut keeps hair and fur, tiny specks of noise are removed
    a = np.clip((a - 0.15) / 0.7, 0.0, 1.0)
    rgba = np.dstack([np.asarray(im.convert("RGB")), (a * 255).astype("uint8")])
    Image.fromarray(rgba, "RGBA").save(dst)
    return {"kept": round(float(a.mean()), 3)}
