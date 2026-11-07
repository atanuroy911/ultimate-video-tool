"""Run every browser suite in client/studio/e2e against a running Studio (scratch server) and write one row per suite.

    python scripts/lab/run_e2e.py <studio url> <out.md> [--only a,b] [--timeout 300] [--skip crawl,...]

The Studio must already proxy to a scratch server (see `vt_lab.py scratch start`). A suite is passing when it exits 0; the row says the counts it printed, or the first failing line.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E2E = ROOT / "client" / "studio" / "e2e"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    suites = sorted(p.stem for p in E2E.glob("*.mjs") if not p.stem.startswith("_") and p.stem != "common")
    if a.only:
        suites = [s for s in suites if s in a.only.split(",")]
    suites = [s for s in suites if s not in a.skip.split(",")]
    rows = []
    for name in suites:
        t0 = time.time()
        env = {**__import__("os").environ, "VT_URL": a.url, "VT_PROJECT": "reference"}
        try:
            r = subprocess.run(["node", f"e2e/{name}.mjs"], cwd=E2E.parent, env=env, capture_output=True, text=True, timeout=a.timeout, encoding="utf-8", errors="replace")
            out, code = (r.stdout + r.stderr), r.returncode
        except subprocess.TimeoutExpired as e:
            out, code = ((e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + "\nTIMED OUT", 124
        took = round(time.time() - t0)
        counts = re.findall(r"(\d+) passed, (\d+) failed", out)
        fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("FAIL")]
        wait = re.findall(r"waiting for (.*)", out)
        note = f"{counts[-1][0]} passed, {counts[-1][1]} failed" if counts else ("no counts printed")
        why = (fails[0] if fails else (("waiting for " + wait[0].strip()[:90]) if wait else ("timed out" if code == 124 else (out.strip().splitlines()[-1][:110] if out.strip() else "no output"))))
        rows.append((name, "PASS" if code == 0 else "FAIL", note, why if code != 0 else "", took))
        print(f"{name:28} {'PASS' if code == 0 else 'FAIL':5} {note:24} {took:4}s  {why if code != 0 else ''}", flush=True)
        Path(a.out).write_text("| suite | result | counts | first problem | seconds |\n|---|---|---|---|---|\n" + "\n".join(f"| {n} | {s} | {c} | {w.replace('|', '/')} | {t} |" for n, s, c, w, t in rows) + "\n", encoding="utf-8")
    bad = [r for r in rows if r[1] != "PASS"]
    print(f"\n{len(rows) - len(bad)} of {len(rows)} suites pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
