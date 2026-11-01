"""The recovery script must validate paths and prove bytes before replacing files."""
import hashlib
import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "restore_comfy_models.py"
    spec = importlib.util.spec_from_file_location("restore_comfy_models", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_manifest_and_path_isolation(tmp_path):
    restore = _module()
    manifest = restore.read_manifest(restore.DEFAULT_MANIFEST)
    assert len(manifest["models"]) == 20
    assert sum(model["size"] for model in manifest["models"]) > 120_000_000_000
    with pytest.raises(ValueError, match="unsafe"):
        restore.checked_path(tmp_path, "../outside.safetensors")


def test_resumed_download_is_hash_checked_before_replace(tmp_path, monkeypatch):
    restore = _module()
    content = b"verified model bytes"
    target = tmp_path / "models" / "test.safetensors"
    target.parent.mkdir()
    partial = target.with_name(target.name + ".part")
    partial.write_bytes(content[:8])
    model = {"path": "test.safetensors", "size": len(content),
             "sha256": hashlib.sha256(content).hexdigest(), "url": "https://huggingface.co/example"}

    class Response:
        status = 206
        headers = {"Content-Range": f"bytes 8-{len(content) - 1}/{len(content)}"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _):
            block = getattr(self, "block", content[8:])
            self.block = b""
            return block

    monkeypatch.setattr(restore.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    restore.download(model, target)
    assert target.read_bytes() == content
    assert not partial.exists()
