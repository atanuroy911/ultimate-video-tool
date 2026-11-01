"""List, verify or restore the ComfyUI model files recorded in assets/comfy/model-manifest.json.

Examples:
  python scripts/restore_comfy_models.py list
  python scripts/restore_comfy_models.py verify --root /mnt/bigdata/video-tool/comfyui/models
  python scripts/restore_comfy_models.py download --root /mnt/bigdata/video-tool/comfyui/models
  python scripts/restore_comfy_models.py download --only checkpoints/ltx-2.3-22b-distilled-fp8.safetensors
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


_BUNDLED_MANIFEST = Path(__file__).resolve().with_name("model-manifest.json")
DEFAULT_MANIFEST = (_BUNDLED_MANIFEST if _BUNDLED_MANIFEST.exists()
                    else Path(__file__).resolve().parents[1] / "assets" / "comfy" / "model-manifest.json")
CHUNK = 8 * 1024 * 1024


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            sha.update(chunk)
    return sha.hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError(f"unsafe model path: {relative}")
    target = root / rel
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"model path leaves destination: {relative}")
    return target


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("models"), list):
        raise ValueError("unsupported model manifest")
    seen = set()
    for model in data["models"]:
        rel = model["path"]
        if rel in seen or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"duplicate or unsafe model path: {rel}")
        seen.add(rel)
        if not model["url"].startswith("https://huggingface.co/"):
            raise ValueError(f"unexpected download host for {rel}")
        if len(model["sha256"]) != 64 or model["size"] <= 0:
            raise ValueError(f"invalid size or hash for {rel}")
    return data


def download(model: dict, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if partial.is_symlink():
        raise RuntimeError(f"partial download is a symlink: {partial}")
    expected = model["size"]
    if partial.exists() and partial.stat().st_size > expected:
        raise RuntimeError(f"partial download is larger than expected: {partial}")
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(model["url"], headers={"User-Agent": "VideoTool-model-restore/1"})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    if offset != expected:
        with urllib.request.urlopen(request, timeout=120) as response:
            status = response.status
            if offset and status != 206:
                offset = 0  # the server ignored Range; begin a clean download
            if offset and status == 206 and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                raise RuntimeError(f"server resumed at an unexpected offset for {model['path']}")
            mode = "ab" if offset else "wb"
            with partial.open(mode) as output:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    output.write(block)
    actual_size = partial.stat().st_size
    if actual_size != expected:
        raise RuntimeError(f"incomplete {model['path']}: {actual_size:,} of {expected:,} bytes; rerun to resume")
    actual_hash = digest(partial)
    if actual_hash != model["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch for {model['path']}; kept {partial} for inspection")
    os.replace(partial, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "verify", "download"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, help="destination models directory; defaults to the recorded big-disk path")
    parser.add_argument("--only", action="append", help="relative model path; repeat to select several")
    args = parser.parse_args(argv)
    manifest = read_manifest(args.manifest)
    root = args.root or Path(manifest["default_root"])
    selected = set(args.only or [])
    known = {model["path"] for model in manifest["models"]}
    if selected - known:
        parser.error("unknown model path(s): " + ", ".join(sorted(selected - known)))
    errors = 0
    for model in manifest["models"]:
        rel = model["path"]
        if selected and rel not in selected:
            continue
        target = checked_path(root, rel)
        if args.action == "list":
            print(f"{model['size'] / 1e9:6.2f} GB  {rel}\n           {model['url']}")
            continue
        if target.exists():
            if target.stat().st_size == model["size"] and digest(target) == model["sha256"]:
                print(f"OK       {rel}", flush=True)
                continue
            if args.action == "download":
                print(f"MISMATCH {rel}; existing file retained", file=sys.stderr)
                errors += 1
                continue
        if args.action == "verify":
            print(f"MISSING  {rel}" if not target.exists() else f"MISMATCH {rel}", flush=True)
            errors += 1
            continue
        print(f"GET      {rel}", flush=True)
        try:
            download(model, target)
            print(f"OK       {rel}", flush=True)
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            print(f"FAILED   {rel}: {exc}", file=sys.stderr, flush=True)
            errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
