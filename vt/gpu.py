"""One place that makes the GPU libraries findable and says which provider ran.

The CUDA 12 runtime (cuBLAS, cuDNN) comes from the torch wheel's `lib` folder; ONNX Runtime (GPU build) and CTranslate2 both load it from there, so the whole app has one set of CUDA libraries.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_done = False


def prepare() -> None:
    """On Windows, let this process find torch's CUDA DLLs. Safe to call many times; does nothing elsewhere."""
    global _done
    if _done or sys.platform != "win32":
        _done = True
        return
    _done = True
    try:
        import torch  # noqa: F401  (importing torch registers its own DLL directory)
        lib = Path(torch.__file__).parent / "lib"
        if lib.exists():
            os.add_dll_directory(str(lib))
            os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def onnx_providers(gpu: bool = True) -> list[str]:
    """CUDA first when the installed ONNX Runtime has it, then CPU. (TensorRT is never used: it builds engines on first run.)"""
    prepare()
    import onnxruntime as ort
    have = ort.get_available_providers()
    return [p for p in (("CUDAExecutionProvider",) if gpu else ()) + ("CPUExecutionProvider",) if p in have]


def cuda_for_onnx() -> bool:
    return "CUDAExecutionProvider" in onnx_providers()


_nvenc_cache: bool | None = None


def has_nvenc() -> bool:
    """Check if ffmpeg has h264_nvenc encoder available and working."""
    global _nvenc_cache
    if _nvenc_cache is not None:
        return _nvenc_cache
    try:
        from .util import find_tool, run
        ff = find_tool("ffmpeg")
        encs = run([ff, "-hide_banner", "-encoders"], check=False)
        _nvenc_cache = "h264_nvenc" in (encs or "")
    except Exception:
        _nvenc_cache = False
    return _nvenc_cache


def gpu_info() -> dict:
    """Detailed hardware GPU, CUDA, and encoder diagnostics."""
    prepare()
    info = {
        "available": False,
        "name": None,
        "device_count": 0,
        "cuda_version": None,
        "vram_mb": None,
        "vram_free_mb": None,
        "nvenc_available": has_nvenc(),
        "onnx_cuda": False,
        "ctranslate2_cuda": False,
        "backend": "cpu",
    }
    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["device_count"] = torch.cuda.device_count()
            info["name"] = torch.cuda.get_device_name(0)
            info["cuda_version"] = torch.version.cuda
            props = torch.cuda.get_device_properties(0)
            info["vram_mb"] = int(props.total_memory / (1024 * 1024))
            try:
                free_b, _ = torch.cuda.mem_get_info(0)
                info["vram_free_mb"] = int(free_b / (1024 * 1024))
            except Exception:
                pass
            info["backend"] = "cuda"
    except Exception:
        pass

    try:
        import onnxruntime as ort
        info["onnx_cuda"] = "CUDAExecutionProvider" in ort.get_available_providers()
    except Exception:
        pass

    try:
        import ctranslate2
        info["ctranslate2_cuda"] = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        pass

    return info
