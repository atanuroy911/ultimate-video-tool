"""Run three real typed scripts through the Studio API and inspect the exported videos.

Set VT_PROJECTS to a dedicated directory before running to keep QA projects separate.
No model, renderer, TTS, or API calls are mocked.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vt import paths  # noqa: E402
from vt.server.app import app  # noqa: E402
from vt.util import find_tool, read_json  # noqa: E402

SCRIPTS = [
    ("story", "The lost wallet", "A woman found a wallet on the train. She could have kept the money, but she called the owner instead. The owner arrived in tears. That small honest choice gave a stranger hope.", "stick"),
    ("explainer", "Why passwords fail", "A short password is easy to guess. Use a long, unique passphrase for every account. Turn on two factor authentication. A password manager can remember the passphrases for you.", "explainer"),
    ("product", "A calmer task list", "Meet a task list that starts with one priority. Add your work, choose what matters today, and hide the rest. At the end of the day, see what you finished and plan tomorrow.", "explainer"),
]


def probe(video: Path) -> dict:
    result = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height", "-of", "json", str(video)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {"seconds": round(float(data["format"]["duration"]), 2), "bytes": int(data["format"]["size"]),
            "width": video_stream.get("width"), "height": video_stream.get("height"),
            "video_codec": video_stream.get("codec_name"), "audio_codec": audio_stream.get("codec_name")}


def main() -> int:
    out = paths.PROJECTS.parent
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "live-script-report.json"
    report = {"at": datetime.now(timezone.utc).isoformat(), "projects_dir": str(paths.PROJECTS), "results": []}
    with TestClient(app) as client:
        for label, title, script, kind in SCRIPTS:
            row = {"case": label, "title": title, "script": script, "kind": kind, "status": "starting"}
            report["results"].append(row)
            try:
                response = client.post("/api/projects/from-script", json={"title": title, "script": script, "engine": "kokoro", "voice": "af_heart", "language": "en", "aspect": "9:16", "theme": "paper", "kind": kind, "usecase": "product" if label == "product" else "story" if label == "story" else "general", "start": True})
                response.raise_for_status()
                payload = response.json()
                pid = payload["project"]["id"]
                row["project_id"] = pid
                job_id = payload["job"]["id"]
                deadline = time.monotonic() + 1200
                while time.monotonic() < deadline:
                    job = client.get(f"/api/jobs/{job_id}").json()
                    if job["status"] in ("done", "error", "cancelled"):
                        break
                    time.sleep(2)
                else:
                    raise TimeoutError("pipeline exceeded 20 minutes")
                row["job_status"] = job["status"]
                row["job_error"] = job.get("error")
                project = paths.PROJECTS / pid
                row["stages"] = list((read_json(project / "project.json") or {}).get("stages", {}))
                row["words"] = len((read_json(project / "transcript.json") or {}).get("words", []))
                row["scenes"] = len((read_json(project / "scenes.json") or {}).get("scenes", []))
                row["publish_kit"] = (project / "publish.json").is_file()
                videos = sorted((project / "exports").glob("*.mp4"))
                row["exports"] = [{"path": str(video), **probe(video)} for video in videos]
                row["scorecards"] = [str(path) for path in (project / "exports").glob("*.retention.json")]
                row["status"] = "passed" if job["status"] == "done" and row["words"] > 0 and row["scenes"] > 0 and row["exports"] and row["publish_kit"] and row["scorecards"] else "failed"
            except Exception as exc:
                row["status"] = "failed"
                row["error"] = f"{type(exc).__name__}: {exc}"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"{label}: {row['status']} ({row.get('project_id', 'no project')})", flush=True)
    return 0 if all(row["status"] == "passed" for row in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
