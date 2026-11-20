"""The version the Release workflow gives an automatic release (a push to main, or a manual run with no version).

    python scripts/next_version.py            # reads the files' version and the repository's tags

Only tags with the same major number as the files count: while the files say 0.x, an old v1.0.0 tag is ignored, so the
automatic number never jumps back to 1.x by accident. The result is the newest such tag plus one patch step, and never lower
than the files' own version (so a hand-made step such as 0.6.0 is respected). With no such tag, it is the files' version.
A pushed tag, or a version typed into a manual run, is explicit and does not go through here.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PLAIN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse(version: str) -> tuple[int, int, int]:
    m = PLAIN.match(version.strip())
    if not m:
        raise ValueError(f"'{version}' is not a version like 0.5.0")
    return int(m[1]), int(m[2]), int(m[3])


def next_version(files: str, tags: list[str]) -> str:
    f = parse(files)
    same = [parse(t) for t in tags if PLAIN.match(t.strip()) and parse(t)[0] == f[0]]
    if not same:
        return files.strip()
    a, b, c = max(same)
    return ".".join(map(str, max((a, b, c + 1), f)))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = subprocess.run([sys.executable, str(root / "scripts" / "set_version.py"), "--show"], capture_output=True, text=True, check=True).stdout.strip()
    tags = subprocess.run(["git", "tag", "-l", "v[0-9]*.[0-9]*.[0-9]*"], capture_output=True, text=True, check=True, cwd=root).stdout.split()
    print(next_version(files, tags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
