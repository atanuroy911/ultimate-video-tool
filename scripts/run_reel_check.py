"""Make one real reel end to end through the running Studio and print what happened: plan (pictures drawn on the GPU server), render, then frames to look at.

    python scripts/run_reel_check.py --url http://127.0.0.1:8777 --project <id> [--from plan]

Reads nothing secret. The project must already exist (made from a script with options {"look": "reel"}).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request


def call(base: str, path: str, body: dict | None = None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def wait(base: str, job_id: str, label: str, limit: float = 2400) -> dict:
    started, last = time.time(), ""
    while time.time() - started < limit:
        j = call(base, f"/api/jobs/{job_id}")
        line = f"{label}: {j['status']} {j.get('stage') or ''} {round(j.get('frac', 0) * 100)}% {j.get('msg', '')[:70]}"
        if line != last:
            print(line, flush=True)
            last = line
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(10)
    raise SystemExit(f"{label}: no end after {limit} s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8777")
    ap.add_argument("--project", required=True)
    ap.add_argument("--from-stage", default="plan")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--only-export", action="store_true")
    a = ap.parse_args()
    if not a.only_export:
        job = wait(a.url, call(a.url, f"/api/projects/{a.project}/run", {"from_stage": a.from_stage, "force": True})["id"], "pipeline")
        if job["status"] != "done":
            raise SystemExit(f"pipeline {job['status']}: {job.get('error', '')[:300]}")
    if not a.no_export:
        job = wait(a.url, call(a.url, f"/api/projects/{a.project}/export", {"aspects": ["9:16"], "quality": "looks"})["id"], "export", 1500)
        if job["status"] != "done":
            raise SystemExit(f"export {job['status']}: {job.get('error', '')[:300]}")
        print("exports:", [f["name"] for f in call(a.url, f"/api/projects/{a.project}/exports")])


if __name__ == "__main__":
    main()
