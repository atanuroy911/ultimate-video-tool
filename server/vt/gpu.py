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
    if _done:
        return
    _done = True
    if sys.platform.startswith("linux"):
        _load_linux_cuda_libs()
        return
    if sys.platform != "win32":
        return
    try:
        import torch  # noqa: F401  (importing torch registers its own DLL directory)
        lib = Path(torch.__file__).parent / "lib"
        if lib.exists():
            os.add_dll_directory(str(lib))
            os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def _load_linux_cuda_libs() -> None:
    """Speech recognition (CTranslate2) needs cuBLAS and cuDNN. When they come from pip (nvidia-cublas-cu12, nvidia-cudnn-cu12) they sit in
    the environment's site-packages, where the dynamic loader does not look, and the first GPU decode fails with "libcublas.so.12 not found"
    (then runs on the CPU, 10x slower). Loading them here by path, before CTranslate2 starts, needs no launcher variable and no system
    install. Libraries the system already provides are used as they are."""
    import ctypes
    import importlib.util

    for pkg, names in (("nvidia.cublas", ("libcublasLt.so.12", "libcublas.so.12")),
                       ("nvidia.cudnn", ("libcudnn_ops.so.9", "libcudnn_cnn.so.9", "libcudnn_graph.so.9", "libcudnn_engines_runtime_compiled.so.9",
                                         "libcudnn_engines_precompiled.so.9", "libcudnn_heuristic.so.9", "libcudnn_adv.so.9", "libcudnn.so.9"))):
        try:
            spec = importlib.util.find_spec(pkg)
        except (ImportError, ValueError):
            continue
        for base in (list(spec.submodule_search_locations) if spec and spec.submodule_search_locations else []):
            lib = Path(base) / "lib"
            for n in names:
                if (lib / n).exists():
                    try:
                        ctypes.CDLL(str(lib / n), mode=ctypes.RTLD_GLOBAL)
                    except OSError:
                        pass


def onnx_providers(gpu: bool = True) -> list:
    """CUDA first when the installed ONNX Runtime has it, on the card chosen as the primary one (Server page, `vt gpu`), then the CPU.
    (TensorRT is never used: it builds engines on first run.) Without this the first card by number would be used, whoever else is working on it."""
    prepare()
    import onnxruntime as ort
    have = ort.get_available_providers()
    out: list = []
    if gpu and usable() and "CUDAExecutionProvider" in have:
        try:
            from . import gpuassign

            out.append(("CUDAExecutionProvider", {"device_id": gpuassign.cuda_index("speech")}))
        except Exception:                                               # noqa: BLE001
            out.append("CUDAExecutionProvider")
    if "CPUExecutionProvider" in have:
        out.append("CPUExecutionProvider")
    return out


def usable() -> bool:
    """False when this computer has NVIDIA cards and Video Tool may use none of them (then nothing of ours draws, encodes or computes on a card). True with no card at all: nothing to forbid."""
    try:
        from . import gpuassign

        return not gpuassign.blocked()
    except Exception:                                                   # noqa: BLE001
        return True


def nvenc_device() -> list[str]:
    """ffmpeg's `-gpu N` for the card the render job uses, counted the way CUDA counts the cards this process sees. Empty when that is not known: ffmpeg then takes the first one it sees."""
    try:
        from . import gpuassign

        card, _ = gpuassign.resolve("render")
        return ["-gpu", str(gpuassign.cuda_index("render"))] if card else []
    except Exception:                                                   # noqa: BLE001
        return []


def torch_device(job: str = "speech") -> str:
    """'cuda:N' for PyTorch on the card the job uses, or 'cpu' when there is no CUDA or Video Tool may use no card."""
    try:
        import torch

        from . import gpuassign

        if not torch.cuda.is_available() or gpuassign.blocked():
            return "cpu"
        return f"cuda:{gpuassign.cuda_index(job)}"
    except Exception:                                                   # noqa: BLE001
        return "cpu"


def cuda_for_onnx() -> bool:
    return any((p[0] if isinstance(p, tuple) else p) == "CUDAExecutionProvider" for p in onnx_providers())


_nvenc_cache: bool | None = None


def has_nvenc() -> bool:
    """ffmpeg has the h264_nvenc encoder, and Video Tool may use a graphics card to run it."""
    global _nvenc_cache
    if _nvenc_cache is None:
        try:
            from .util import find_tool, run
            ff = find_tool("ffmpeg")
            encs = run([ff, "-hide_banner", "-encoders"], check=False)
            _nvenc_cache = "h264_nvenc" in (encs or "")
        except Exception:
            _nvenc_cache = False
    return _nvenc_cache and usable()


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
