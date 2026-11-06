"""Which GPU does a render really use? Start an export on the server and sample every card every 2 s until it finishes.
    GPU_PASS=... python scripts/lab/gpu_trace.py <project id> [--quality draft] [--aspect 16:9]   (needs dist/recording-run/key.txt, from run_recording.py)
Prints per card: peak load, peak encoder load, peak memory, and the seconds above 5 % load: the proof for "the RTX 3060 did the work"."""
import argparse
import os
import threading
import time
from pathlib import Path

import httpx
import paramiko

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--quality", default="draft")
ap.add_argument("--aspect", default="16:9")
a = ap.parse_args()
key = (Path(__file__).resolve().parents[2] / "dist/recording-run/key.txt").read_text().strip()
c = httpx.Client(base_url="http://192.168.123.47:8790", headers={"Authorization": f"Bearer {key}"}, timeout=60)
samples: list[tuple[float, list[list[str]]]] = []
stop = threading.Event()


def sampler() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], look_for_keys=False, allow_agent=False, timeout=20)
    while not stop.is_set():
        _, o, _ = ssh.exec_command("nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.encoder,utilization.decoder,memory.used --format=csv,noheader,nounits")
        rows = [[x.strip() for x in line.split(",")] for line in o.read().decode().splitlines() if line.strip()]
        samples.append((time.time(), rows))
        time.sleep(2)
    ssh.close()


t = threading.Thread(target=sampler, daemon=True)
t.start()
time.sleep(4)                                                       # a few quiet samples first
r = c.post(f"/api/projects/{a.project}/export", json={"aspects": [a.aspect], "quality": a.quality, "gpu": True, "music": "project", "captions": True})
r.raise_for_status()
job = r.json()["id"]
t0 = time.time()
while True:
    try:
        j = c.get(f"/api/jobs/{job}").json()
    except httpx.HTTPError:                                         # a dropped connection is not the end of the export: ask again
        time.sleep(5)
        continue
    if j["status"] in ("done", "error", "cancelled"):
        break
    time.sleep(5)
time.sleep(4)
stop.set()
t.join(10)
print(f"export {j['status']} in {time.time() - t0:.0f} s")
cards: dict[str, dict] = {}
for ts, rows in samples:
    for r_ in rows:
        name = f"GPU {r_[0]} {r_[1]}"
        d = cards.setdefault(name, {"gpu": [], "enc": [], "dec": [], "mem": []})
        for k, v in zip(("gpu", "enc", "dec", "mem"), r_[2:6]):
            d[k].append(float(v) if v.replace(".", "").isdigit() else 0.0)
for name, d in cards.items():
    busy = sum(1 for v in d["gpu"] if v >= 5) * 2
    print(f"{name:34} load peak {max(d['gpu']):3.0f}%  encoder peak {max(d['enc']):3.0f}%  decoder peak {max(d['dec']):3.0f}%  memory {min(d['mem']):.0f}->{max(d['mem']):.0f} MiB  seconds above 5% load: {busy}")
