"""Multilingual text embeddings (intfloat/multilingual-e5-small, MIT) used to match words to icons by meaning.

The same model embeds English dictionary entries, icon descriptions and, at planning time, Bangla words and whole sentences,
so one icon index serves every language the model knows.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np

from .. import paths

MODEL_ID = "intfloat/multilingual-e5-small"
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def model_dir():
    return paths.MODELS / "e5-small"


def ensure_model() -> str:
    """Download once into models/e5-small (about 470 MB) and return the folder."""
    d = model_dir()
    if (d / "model.safetensors").exists():
        return str(d)
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID, local_dir=str(d), allow_patterns=["*.json", "*.txt", "model.safetensors", "sentencepiece*", "tokenizer*"])
    return str(d)


class Embedder:
    """Mean-pooled, L2-normalised sentence vectors. Runs on the GPU when available, otherwise the CPU."""

    _inst: Optional["Embedder"] = None

    @classmethod
    def get(cls) -> "Embedder":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self, device: Optional[str] = None):
        import torch
        from transformers import AutoModel, AutoTokenizer

        path = ensure_model()
        self.torch = torch
        from .. import gpu

        self.device = device or gpu.torch_device()                       # the card chosen for speech and listening, or the processor
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModel.from_pretrained(path, torch_dtype=torch.float16 if self.device.startswith("cuda") else torch.float32).to(self.device).eval()

    def encode(self, texts: list[str], prefix: str = "query: ", batch: int = 256, max_len: int = 48) -> np.ndarray:
        torch = self.torch
        out = []
        order = np.argsort([len(t) for t in texts])           # length-sorted batches waste less padding
        for i in range(0, len(texts), batch):
            idx = order[i: i + batch]
            enc = self.tok([prefix + texts[j] for j in idx], padding=True, truncation=True, max_length=max_len, return_tensors="pt").to(self.device)
            with torch.no_grad():
                h = self.model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
            v = (h * m).sum(1) / m.sum(1).clamp(min=1)
            v = torch.nn.functional.normalize(v.float(), dim=-1)
            out.append(v.cpu().numpy())
        mat = np.concatenate(out) if out else np.zeros((0, 384), dtype=np.float32)
        res = np.empty_like(mat)
        res[order] = mat
        return res
