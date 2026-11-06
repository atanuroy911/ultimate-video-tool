"""Put the current server code on the GPU server's app folder and restart its service (refuses while a job is running).
    GPU_PASS=... python scripts/lab/deploy_server_code.py [--primary "NVIDIA GeForce RTX 3060"]
The launcher no longer pins CUDA_VISIBLE_DEVICES: Video Tool chooses its own card per job (vt/gpuassign.py, Server page); the primary card is saved in settings."""
import argparse
import io
import os
import tarfile
import time
from pathlib import Path

import httpx
import paramiko

ap = argparse.ArgumentParser()
ap.add_argument("--primary", default="")
ap.add_argument("--force", action="store_true", help="restart even when a job is running")
a = ap.parse_args()
ROOT = "/home/roy/ultimate-video-tool-server"
repo = Path(__file__).resolve().parents[2]
key = (repo / "dist/recording-run/key.txt").read_text().strip()
api = httpx.Client(base_url="http://192.168.123.47:8790", headers={"Authorization": f"Bearer {key}"}, timeout=60)

jobs = [j for j in api.get("/api/jobs").json() if j["status"] in ("queued", "running") and j["kind"] in ("pipeline", "export")]
if jobs and not a.force:
    raise SystemExit(f"{len(jobs)} job(s) are running ({jobs[0]['label']}); not restarting. Use --force to override.")

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as t:
    for p in sorted((repo / "server/vt").rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            t.add(p, arcname="vt/" + p.relative_to(repo / "server/vt").as_posix())
    for p in sorted((repo / "server/renderer/runtime").rglob("*")):                       # the renderer's own scripts and styles (server/renderer/runtime)
        if p.is_file():
            t.add(p, arcname="renderer/runtime/" + p.relative_to(repo / "server/renderer/runtime").as_posix())
    for p in sorted((repo / "server/renderer/scripts").glob("*.mjs")):
        t.add(p, arcname="renderer/scripts/" + p.name)
    t.add(repo / "server/design/icons/emoji/1fa99.svg", arcname="design/icons/emoji/1fa99.svg")
buf.seek(0)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], look_for_keys=False, allow_agent=False, timeout=20)
s = c.open_sftp()
with s.file(f"{ROOT}/vt-code.tgz", "wb") as f:
    f.write(buf.getvalue())
s.close()
cmd = f"""set -e; cd {ROOT}/app && tar -xzf ../vt-code.tgz && rm ../vt-code.tgz && rm -f vt/server/clients.py vt/server/__pycache__/clients.*.pyc       # files the product no longer has (pairing, 2026-11-05)
sed -i '/^export CUDA_VISIBLE_DEVICES=/d' {ROOT}/run-server.sh
grep -q CUDA_DEVICE_ORDER {ROOT}/run-server.sh || sed -i 's|^cd "\\$ROOT/app"$|export CUDA_DEVICE_ORDER=PCI_BUS_ID\\ncd "$ROOT/app"|' {ROOT}/run-server.sh
grep -n "CUDA" {ROOT}/run-server.sh
systemctl --user restart ultimate-video-tool.service"""
_, out, err = c.exec_command(cmd)
print(out.read().decode().strip(), err.read().decode().strip())
c.close()
for _ in range(40):
    time.sleep(2)
    try:
        if api.get("/api/health").status_code == 200:
            break
    except httpx.HTTPError:
        pass
print("health:", api.get("/api/health").json())
if a.primary:
    r = api.put("/api/system/gpu", json={"primary": a.primary})
    print("primary ->", r.status_code, {k: v["name"] for k, v in r.json().get("jobs", {}).items()} if r.status_code == 200 else r.text[:200])
d = api.get("/api/system/gpus").json()
print("cards:", [(c_["index"], c_["name"], c_["allowed"]) for c_ in d["cards"]], "| saved:", d["saved"], "| pinned:", d["pinned_by_launcher"])
st = api.get("/api/system/stats").json()
print("system:", st["host"]["name"], "cpu", st["cpu"]["percent"], "% mem", st["memory"]["percent"], "% gpus", [(g["name"], g["percent"], [p["label"] for p in g["programs"]]) for g in st["gpus"]])
