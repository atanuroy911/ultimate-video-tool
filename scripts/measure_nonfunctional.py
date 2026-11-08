"""Measure the non-functional numbers of docs/TEST-PLAN.md section 6 that can be measured on one machine, and write docs/evidence/<date>/nonfunctional.md.

    python scripts/measure_nonfunctional.py [--video path.mp4]

What it measures: start-up import time, the speed of the Studio's commonest API calls (median and 95th percentile over 40 calls), how long the judges take on a real video and how much
memory they use. Nothing here needs a GPU server. The numbers describe THIS computer; the file says which.
"""
from __future__ import annotations

import argparse
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1e6
    except Exception:                                                                  # noqa: BLE001
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(ROOT / "docs" / "evidence" / "2026-10-28" / "reel-voiced-by-breeze-9x16.mp4"))
    a = ap.parse_args()
    rows: list[tuple[str, str]] = []
    t = time.time()
    out = subprocess.run([sys.executable, "-X", "importtime", "-c", "import vt.server.app"], capture_output=True, text=True, cwd=ROOT)
    rows.append(("Start-up: `import vt.server.app` (cold process)", f"{time.time() - t:.1f} s" + ("" if out.returncode == 0 else " (FAILED)")))

    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="vt-nf-")
    os.environ["VT_DATA"] = tmp
    from vt.server.app import app

    with TestClient(app) as c:
        for path in ("/api/health", "/api/projects", "/api/engines?health=false", "/api/setup/hardware", "/api/themes"):
            times = []
            for _ in range(40):
                s = time.perf_counter()
                c.get(path)
                times.append((time.perf_counter() - s) * 1000)
            times.sort()
            rows.append((f"`GET {path}`", f"median {statistics.median(times):.0f} ms, p95 {times[int(len(times) * 0.95) - 1]:.0f} ms"))
    video = Path(a.video)
    if video.exists():
        from vt.judges import judge_video

        before = rss_mb()
        s = time.time()
        r = judge_video(video)
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
        rows.append((f"Judges on `{video.name}` ({float(dur or 0):.0f} s of video)", f"{time.time() - s:.1f} s, memory {before:.0f} -> {rss_mb():.0f} MB, {len(r['verdicts'])} judges"))
    else:
        rows.append(("Judges", f"skipped: {video} does not exist"))
    cpu = platform.processor() or platform.machine()
    lines = [f"# Non-functional measurements, {date.today().isoformat()}", "", f"Machine: {platform.system()} {platform.release()}, {cpu}, {os.cpu_count()} logical cores, Python {platform.python_version()}.",
             "Measured by `scripts/measure_nonfunctional.py`; these describe this computer only.", "", "| What | Result |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows]
    dest = ROOT / "docs" / "evidence" / date.today().isoformat() / "nonfunctional.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
