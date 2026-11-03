"""Every model the app downloads, in one table, and one way to fetch them.

A model is a folder under `models/` with files whose size (and, where known, SHA-256) is pinned here. `ensure()` downloads what is missing into `<file>.part`, resumes an interrupted
download with an HTTP Range request, checks size and hash, and only then renames it, so a torn download is never mistaken for a model.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import paths

Progress = Callable[[float, str], None]


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class File:
    rel: str                          # path inside the model's folder
    bytes: int
    url: str
    sha256: str = ""


@dataclass(frozen=True)
class Model:
    id: str
    title: str
    folder: str
    licence: str
    files: tuple[File, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return sum(f.bytes for f in self.files)

    @property
    def dir(self) -> Path:
        return paths.MODELS / self.folder


_TURBO = "https://huggingface.co/ResembleAI/chatterbox-turbo-ONNX/resolve/d21799bd0354adb85e348b8a0442a8405110a2cf/"


def _turbo(rel: str, size: int, sha: str) -> File:
    return File(rel, size, _TURBO + rel, sha)


_KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"

MODELS: dict[str, Model] = {m.id: m for m in (
    Model("chatterbox-turbo", "Voice cloning (Chatterbox Turbo, ONNX)", "chatterbox-turbo", "MIT", (          # smallest first, so a torn download costs the least
        _turbo("tokenizer.json", 3_562_272, "3f04e34bea22f9144d1a19151154095bc9ce0430bf421304f5797e716288a906"),
        _turbo("onnx/embed_tokens_quantized.onnx", 2_887, "0efe1bc01c2c48a98425a74444fd9887924d887f922c2722a6ec961ebb9e1db6"),
        _turbo("onnx/language_model_quantized.onnx", 279_670, "0b40581277e30b7034331ec8c3ad47ed71d321f015b387a95221e54e2fcbfde8"),
        _turbo("onnx/speech_encoder_quantized.onnx", 1_205_728, "5b6f15870a43cf97892df86fc550a0ef4763522d527cde72b2a4316f80a34de4"),
        _turbo("onnx/conditional_decoder_quantized.onnx", 2_202_035, "2af3b150196d9d559cd3c91e03da80eb27a466032369dc2b57ea729cddad3ebb"),
        _turbo("onnx/embed_tokens_quantized.onnx_data", 67_297_376, "9025d04c124899823124b1d7bb7069b1f535fb8a6c2d88f97520eb6fecced986"),
        _turbo("onnx/conditional_decoder_quantized.onnx_data", 326_548_688, "4918ca09e05e41d2b4aa1ace6201d1cd911ffc58a42801002bab177d495cfe0a"),
        _turbo("onnx/speech_encoder_quantized.onnx_data", 354_676_576, "d59861fb55e806fbeee731da9d4f8ff819fb5735de5d15e262d902594ee4dbb6"),
        _turbo("onnx/language_model_quantized.onnx_data", 367_962_860, "ec9945df36cb5d131d46688f2609fd715fbfcb0b8ee9681af5c84118de2d55a2"),
    )),
    Model("isnet-general-use", "Background removal (IS-Net)", "cutout", "Apache-2.0", (
        File("isnet-general-use.onnx", 178_648_008, "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
             "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"),
    )),
    Model("kokoro", "Offline voices (Kokoro)", "kokoro", "Apache-2.0", (
        File("kokoro-v1.0.int8.onnx", 92_361_271, _KOKORO + "kokoro-v1.0.int8.onnx",
             "6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb"),
        File("voices-v1.0.bin", 28_214_398, _KOKORO + "voices-v1.0.bin",
             "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
    )),
)}

_lock = threading.Lock()


def get(model_id: str) -> Model:
    try:
        return MODELS[model_id]
    except KeyError:
        raise ModelError(f"unknown model '{model_id}'") from None


def _present(m: Model, f: File) -> bool:
    p = m.dir / f.rel
    return p.is_file() and p.stat().st_size == f.bytes


def ready(model_id: str) -> bool:
    m = get(model_id)
    return all(_present(m, f) for f in m.files)


def missing_bytes(model_id: str) -> int:
    m = get(model_id)
    return sum(f.bytes for f in m.files if not _present(m, f))


def _fetch(f: File, target: Path, on_bytes: Callable[[int], None], cancel: Optional[threading.Event]) -> None:
    import httpx

    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    if have > f.bytes:
        part.unlink()
        have = 0
    h = hashlib.sha256()
    if have:                                                                                  # hash the part already on disk, then continue after it
        with part.open("rb") as o:
            for block in iter(lambda: o.read(1 << 22), b""):
                h.update(block)
    if have < f.bytes:
        headers = {"Range": f"bytes={have}-"} if have else {}
        with httpx.stream("GET", f.url, headers=headers, follow_redirects=True, timeout=httpx.Timeout(60.0, read=120.0)) as r:
            if r.status_code == 200 and have:                                                 # the server ignored the Range: start again
                part.unlink()
                have = 0
                h = hashlib.sha256()
            elif r.status_code not in (200, 206):
                r.raise_for_status()
            got = have
            with part.open("ab" if have else "wb") as o:
                for chunk in r.iter_bytes(1 << 20):
                    if cancel is not None and cancel.is_set():
                        raise ModelError("download cancelled")
                    o.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    on_bytes(got)
    if part.stat().st_size != f.bytes or (f.sha256 and h.hexdigest() != f.sha256):
        part.unlink(missing_ok=True)
        raise ModelError(f"{target.name}: the download was damaged")
    part.replace(target)


def ensure(model_id: str, progress: Optional[Progress] = None, cancel: Optional[threading.Event] = None) -> Path:
    """Make sure every file of the model is on disk, whole and as pinned; returns the model's folder."""
    m = get(model_id)
    with _lock:
        todo = [f for f in m.files if not _present(m, f)]
        if not todo:
            return m.dir
        need = sum(f.bytes for f in todo)
        done = 0
        for f in todo:
            base = done

            def on_bytes(n: int, base=base, f=f) -> None:
                if progress:
                    progress(min(0.99, (base + n) / need), f"Downloading {m.title} ({f.rel.rsplit('/', 1)[-1]})")
            try:
                _fetch(f, m.dir / f.rel, on_bytes, cancel)
            except ModelError:
                raise
            except Exception as e:
                raise ModelError(f"{m.title} has to be downloaded once (about {m.total // 1_000_000} MB). Connect to the internet and try again. ({type(e).__name__})") from e
            done += f.bytes
        if progress:
            progress(1.0, f"{m.title} is ready")
    return m.dir
