"""Builds the Engine package: everything a GPU computer needs to become the server for Video Tool, without the Studio window.

    python scripts/make_engine_package.py [--out dist] [--version 1.2.0]

Result in --out:
    video-tool-engine-<version>.zip         the same file for Windows, Linux and macOS
    video-tool-engine-<version>.tar.gz      the same files, for people who prefer tar
    SHA256SUMS-engine.txt                   one line per archive

Inside (one folder, `video-tool-engine/`): the `vt` Python package, the ComfyUI workflows and model manifest, `pyproject.toml` and `uv.lock` (the locked, tested dependency
set), the two install scripts and a short README. It carries no models and no Python: `install-engine.ps1` / `install-engine.sh` fetch `uv`, which installs Python 3.11 and
the locked packages, and then `vt engine setup` downloads Ollama, ComfyUI and the models (docs/plans/PLAN-PACKAGING.MD).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "server"
sys.path.insert(0, str(REPO / "scripts"))
FOLDER = "video-tool-engine"
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# what the engine needs at run time besides the code: the picture/voice workflows and the model list (each is small)
ASSET_DIRS = ["assets/comfy"]
TOP_FILES = ["pyproject.toml", "uv.lock", "LICENSE", "LICENSE.txt", "LICENSE.md"]
PACKAGING = ["install-engine.ps1", "install-engine.sh", "check-engine.py", "README-ENGINE.txt", "Dockerfile", "docker-compose.yml", "docker-entrypoint.sh"]


def _walk(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_dir() or SKIP_DIRS & set(p.relative_to(ROOT).parts) or p.suffix in SKIP_SUFFIX:
            continue
        yield p


def collect(version: str, full: bool = False) -> dict[str, bytes]:
    """{path inside the archive: bytes}. Line endings of text files are kept as they are, except that the shell script is forced to LF (a CRLF script does not run on Linux)."""
    files: dict[str, bytes] = {}
    for p in _walk(ROOT / "vt"):
        files[f"{FOLDER}/{p.relative_to(ROOT).as_posix()}"] = p.read_bytes()
    for d in ASSET_DIRS:
        if (ROOT / d).is_dir():
            for p in _walk(ROOT / d):
                files[f"{FOLDER}/{p.relative_to(ROOT).as_posix()}"] = p.read_bytes()
    if full:
        for directory in ('design', 'renderer/runtime', 'assets'):
            for p in _walk(ROOT / directory):
                if 'user' not in p.relative_to(ROOT).parts and not any(part.startswith('auto-') for part in p.relative_to(ROOT).parts):
                    files[f"{FOLDER}/{p.relative_to(ROOT).as_posix()}"] = p.read_bytes()
        for name in ('renderer/package.json','renderer/package-lock.json'):
            files[f"{FOLDER}/{name}"] = (ROOT/name).read_bytes()
    for name in TOP_FILES:
        if (ROOT / name).is_file():
            files[f"{FOLDER}/{name}"] = (ROOT / name).read_bytes()
    pack = ROOT / "packaging" / "engine"
    for name in PACKAGING:
        src = pack / name
        if not src.is_file():
            raise SystemExit(f"missing packaging file: {src}")
        data = src.read_bytes()
        if name.endswith(".sh") or name == "Dockerfile":
            data = data.replace(b"\r\n", b"\n")
        files[f"{FOLDER}/{name}"] = data
    files[f"{FOLDER}/VERSION"] = (version + "\n").encode()
    meta = {"name": "video-tool-engine", "version": version, "files": len(files)}
    files[f"{FOLDER}/engine-package.json"] = (json.dumps(meta, indent=2) + "\n").encode()
    return files


def write_zip(files: dict[str, bytes], dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if name.endswith((".sh", ".ps1")) else 0o644) << 16
            z.writestr(info, data)


def write_tar(files: dict[str, bytes], dest: Path) -> None:
    with tarfile.open(dest, "w:gz", compresslevel=9) as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 1767225600
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            t.addfile(info, io.BytesIO(data))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--version", default="")
    ap.add_argument("--full", action="store_true", help="Include processing renderer and visual assets. Never includes the separate client editor.")
    a = ap.parse_args()
    from set_version import current

    version = (a.version or current()).lstrip("v")
    if not re.match(r"^\d+\.\d+\.\d+", version):
        raise SystemExit(f"'{version}' is not a version")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = collect(version, full=a.full)
    z, t = out / f"video-tool-engine-{version}.zip", out / f"video-tool-engine-{version}.tar.gz"
    write_zip(files, z)
    write_tar(files, t)
    sums = out / "SHA256SUMS-engine.txt"
    sums.write_text("".join(f"{sha256(p)}  {p.name}\n" for p in (z, t)), encoding="utf-8")
    print(f"{len(files)} files, {z.stat().st_size / 1e6:.1f} MB zip, {t.stat().st_size / 1e6:.1f} MB tar.gz")
    print(z)
    print(t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
