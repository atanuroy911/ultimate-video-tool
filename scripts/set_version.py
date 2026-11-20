"""Put one version number everywhere it is written: pyproject.toml, the lock file's own entry, and the package.json (with its lock file) of both desktop apps, the Studio and the renderer.

    python scripts/set_version.py 1.2.0          # also accepts v1.2.0
    python scripts/set_version.py --show

The release workflow runs this with the tag, so the installers, the engine package and the Python package all carry the number the release is named after.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _read(p: Path) -> str:
    return p.read_bytes().decode("utf-8")


def _write(p: Path, text: str) -> None:
    p.write_bytes(text.encode("utf-8"))                      # byte for byte: the files keep their own line endings


def current() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', _read(ROOT / "server" / "pyproject.toml"), re.M)
    if not m:
        raise SystemExit("pyproject.toml has no version")
    return m.group(1)


def apply(version: str) -> list[str]:
    version = version.lstrip("v")
    if not SEMVER.match(version):
        raise SystemExit(f"'{version}' is not a version like 1.2.0")
    changed = []
    py = ROOT / "server" / "pyproject.toml"
    t = _read(py)
    new = re.sub(r'^(version\s*=\s*)"[^"]+"', rf'\g<1>"{version}"', t, count=1, flags=re.M)
    if new != t:
        _write(py, new)
        changed.append("server/pyproject.toml")
    lock = ROOT / "server" / "uv.lock"
    if lock.exists():
        t = _read(lock)
        new = re.sub(r'(\[\[package\]\]\r?\nname = "video-tool"\r?\nversion = )"[^"]+"', rf'\g<1>"{version}"', t, count=1)
        if new != t:
            _write(lock, new)
            changed.append("server/uv.lock")
    # every package.json that carries our version, and the first entries of its lock file (the project itself)
    for rel in ("client/desktop", "server/desktop", "client/studio", "server/renderer"):
        pj = ROOT / rel / "package.json"
        if pj.exists():
            t = _read(pj)
            new = re.sub(r'^(\s*"version"\s*:\s*)"[^"]+"', rf'\g<1>"{version}"', t, count=1, flags=re.M)
            if new != t:
                _write(pj, new)
                changed.append(f"{rel}/package.json")
            json.loads(new)
        pl = ROOT / rel / "package-lock.json"
        if pl.exists():
            t = _read(pl)
            new = re.sub(r'^(  "version"\s*:\s*)"[^"]+"', rf'\g<1>"{version}"', t, count=1, flags=re.M)
            new = re.sub(r'(^    ""\s*:\s*\{\r?\n\s*"name"\s*:\s*"[^"]+",\r?\n\s*"version"\s*:\s*)"[^"]+"', rf'\g<1>"{version}"', new, count=1, flags=re.M)
            if new != t:
                _write(pl, new)
                changed.append(f"{rel}/package-lock.json")
            json.loads(new)
    return changed


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--show":
        print(current())
        return 0
    changed = apply(argv[0])
    print(f"version {current()}: " + (", ".join(changed) if changed else "already set everywhere"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
