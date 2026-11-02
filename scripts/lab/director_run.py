"""Make the owner's billionaire script into a picture reel and stop at the draft plan, so a director (the local AI, or Claude) can be judged.
    director_run.py <suffix>       -> prints the project id; the plan is in its plan_doc.json"""
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
c = httpx.Client(base_url="http://127.0.0.1:8771", timeout=600)
for _ in range(60):
    try:
        c.get("/api/engines", params={"health": "false"})
        break
    except httpx.HTTPError:
        time.sleep(2)
script = (ROOT / "samples/scripts/billionaire-tax-easy.txt").read_text(encoding="utf-8")
r = c.post("/api/projects/from-script", json={"title": f"Billionaire tax ({sys.argv[1]})", "script": script, "language": "auto", "engine": "edge",
                                             "voice": "en-US-AndrewNeural", "aspect": "9:16", "theme": "style-midcentury-toon", "usecase": "general",
                                             "kind": "explainer", "options": {"look": "reel"}, "start": True})
r.raise_for_status()
b = r.json()
pid, job = b["project"]["id"], b["job"]["id"]
print("project", pid, flush=True)
t = time.time()
while time.time() - t < 1800:
    j = c.get(f"/api/jobs/{job}").json()
    if j["status"] in ("done", "error", "cancelled"):
        break
    time.sleep(10)
print("job", j["status"], j.get("stage"), j.get("error", "")[:300], f"{time.time() - t:.0f} s", flush=True)
