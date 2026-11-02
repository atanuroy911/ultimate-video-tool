"""Draw a project's approved plan through the lab Studio, then render 9:16 and make a contact sheet.  draw_render.py <project-id> <out-name>"""
import json
import shutil
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, r"C:\Users\Roy\Desktop\ultimate-video-tool\scripts")
import video_lab as V  # noqa: E402

PID, NAME = sys.argv[1], sys.argv[2]
API = httpx.Client(base_url="http://127.0.0.1:8771", timeout=600)
D = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\projects") / PID
OUT = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story\one-gpu")
for _ in range(60):
    try:
        API.get("/api/engines", params={"health": "false"})
        break
    except httpx.HTTPError:
        time.sleep(2)
plan = json.loads((D / "plan_doc.json").read_text(encoding="utf-8"))
plan["state"] = "draft"
for m in plan["moments"]:
    if not m.get("media"):
        m.update(status="planned", problem="")
(D / "plan_doc.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
t = time.time()
r = API.post(f"/api/projects/{PID}/plan/approve")
print("approve", r.status_code, flush=True)
time.sleep(8)
while API.get(f"/api/projects/{PID}").json().get("active_job"):
    time.sleep(10)
plan = json.loads((D / "plan_doc.json").read_text(encoding="utf-8"))
missing = [m["id"] for m in plan["moments"] if not m.get("media")]
rep = json.loads((D / "reel_report.json").read_text(encoding="utf-8")) if (D / "reel_report.json").exists() else {}
times = [x.get("drawn_in") for x in rep.get("slots", []) if x.get("drawn_in")]
print(f"drew {len(plan['moments']) - len(missing)}/{len(plan['moments'])} in {(time.time() - t) / 60:.1f} min; per picture {min(times or [0]):.1f}-{max(times or [0]):.1f} s; missing {missing}", flush=True)
j = API.post(f"/api/projects/{PID}/export", json={"aspects": ["9:16"], "quality": "delivery", "gpu": True, "music": "calm-01", "music_volume": 0.12, "captions": True})
j.raise_for_status()
V.wait_job(API, j.json()["id"], "render", 3600)
mp4 = Path(API.get(f"/api/projects/{PID}/exports").json()[0]["path"])
dest = OUT / f"{NAME}.mp4"
shutil.copy(mp4, dest)
d = V.duration(dest)
V.strip(dest, OUT / f"{NAME}.sheet.png", [d * (i + 0.5) / 16 for i in range(16)], 480)
print("DONE", dest, f"{d:.1f}s", flush=True)
