"""One set of CUDA libraries serves torch, ONNX Runtime and CTranslate2 in the same process. Skipped on machines without an NVIDIA GPU."""
import shutil

import pytest

from vt import gpu

pytestmark = pytest.mark.skipif(shutil.which("nvidia-smi") is None, reason="no NVIDIA GPU")


def test_onnx_runtime_has_cuda_and_never_tensorrt():
    p = [x[0] if isinstance(x, tuple) else x for x in gpu.onnx_providers()]                 # a pinned card comes as ("CUDAExecutionProvider", {"device_id": n})
    assert p[0] == "CUDAExecutionProvider" and p[-1] == "CPUExecutionProvider" and "TensorrtExecutionProvider" not in p
    assert gpu.onnx_providers(gpu=False) == ["CPUExecutionProvider"]


def test_only_one_onnx_runtime_package_is_installed():
    from importlib.metadata import PackageNotFoundError, version

    def has(n):
        try:
            version(n)
            return True
        except PackageNotFoundError:
            return False
    assert has("onnxruntime-gpu") and not has("onnxruntime")


def test_torch_onnx_and_ctranslate2_share_the_gpu_in_one_process():
    import numpy as np
    import onnxruntime as ort
    import torch

    gpu.prepare()
    import ctranslate2
    assert torch.cuda.is_available() and ctranslate2.get_cuda_device_count() > 0
    x = torch.randn(64, 64, device="cuda")
    assert float((x @ x).sum()) == float((x @ x).sum())                                         # torch uses cuBLAS
    from vt import cutout
    s = ort.InferenceSession(str(cutout.ensure_model()), providers=gpu.onnx_providers())
    assert s.get_providers()[0] == "CUDAExecutionProvider"
    out = s.run(None, {s.get_inputs()[0].name: np.zeros((1, 3, 1024, 1024), "float32")})
    assert out and out[0].shape[-1] == 1024
    assert float((x @ x).sum()) == float((x @ x).sum())                                         # and torch still works afterwards
