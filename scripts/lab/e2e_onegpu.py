"""End to end on the owner's existing ComfyUI (8188, one card): find it from this PC, make it ready through the API, draw the whole story
with the picture set the fit chose, render, and record the server's card and RAM the whole time (nothing may swap)."""
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import httpx
import paramiko

sys.path.insert(0, r"C:\Users\Roy\Desktop\ultimate-video-tool\scripts")
import video_lab as V  # noqa: E402

API = httpx.Client(base_url="http://127.0.0.1:8771", timeout=600)
ROOT = Path(r"C:\Users\Roy\Videos\Video Tool Lab\story")
PROJ = ROOT / "projects"
SRC = PROJ / "2026-11-01-the-last-lamp"
PID = "the-last-lamp-onegpu"
OUT = ROOT / "one-gpu"
OUT.mkdir(exist_ok=True)
log = open(OUT / "e2e.log", "a", encoding="utf-8")


def say(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


def check(cond, what):
    say("PASS" if cond else "FAIL", what)
    if not cond:
        raise SystemExit(1)


# ---- 1. found from this PC: the server's ComfyUI with its card, Ollama, and not the chat site on 3000
t = time.time()
found = API.get("/api/discover", params={"host": "192.168.123.47"}).json()
comfy = [i for i in found["instances"] if i["engine"] == "comfy"]
say(f"scan {time.time() - t:.1f}s:", [(i["engine"], i["port"], i.get("gpu", ""), (i.get("fit") or {}).get("recipe")) for i in found["instances"]])
check(any(i["port"] == 8188 and "3060" in i["gpu"] for i in comfy), "ComfyUI 8188 found with its card")
check(not any(i["port"] == 3000 for i in found["instances"]), "the chat site on 3000 is not taken for Ollama")
check(any(i["engine"] == "ollama" and i["port"] == 11434 for i in found["instances"]), "Ollama 11434 found")
check(all(i["port"] != 8189 for i in found["instances"]), "the stopped ComfyUI 8189 is not listed")
c8188 = next(i for i in comfy if i["port"] == 8188)
check(c8188["fit"]["recipe"] == "zimage-fp8", f"8-bit set chosen for the 12 GB RTX 3060 ({c8188['fit']['why']})")
nobody = API.get("/api/discover", params={"host": "192.168.123.250"}).json()
check(nobody["instances"] == [] and nobody["next"]["comfy"] == "install", "an address with nothing on it: offer to install")

# ---- 2. ready through the API (the files are on the server now: nothing to download)
plan = API.get("/api/discover/prepare", params={"url": "http://192.168.123.47:8188"}).json()
say("plan:", plan["label"], [(f["file"], f["have"]) for f in plan["files"]], plan["problems"])
check(plan["download_gb"] == 0 and not plan["problems"], "everything for the 8-bit set is on that ComfyUI")
job = API.post("/api/discover/prepare", json={"url": "http://192.168.123.47:8188"}).json()
V.wait_job(API, job["id"], "prepare", 300)
s = json.loads(Path(r"C:\Users\Roy\Desktop\ultimate-video-tool\settings.json").read_text(encoding="utf-8"))
check(s.get("picture_recipe") == "zimage-fp8" and s["engines"]["comfy"]["workers"] == [], "Video Tool uses 8188 with the 8-bit set; the gone worker is dropped")

# ---- 3. the whole story, watched
samples = []
stop = threading.Event()


def watch():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], timeout=15, look_for_keys=False, allow_agent=False)
    while not stop.is_set():
        _, o, _ = ssh.exec_command("nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits; free -m | awk '/Mem/{print $7} /Swap/{print $3}'")
        v = o.read().decode().split()
        try:                                       # "0," used "1," used avail_mb swap_mb
            samples.append({"t": time.time(), "v100_mb": int(v[1]), "rtx3060_mb": int(v[3]), "ram_avail_mb": int(v[4]), "swap_mb": int(v[5])})
        except Exception:
            samples.append({"t": time.time(), "raw": v})
        time.sleep(5)
    ssh.close()


dst = PROJ / PID
if not dst.exists():
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("exports", "composition", "snapshots", "media", "comfy_stills.json", "reel_report.json", "cover_*", "qa_frames"))
    meta = json.loads((dst / "project.json").read_text(encoding="utf-8"))
    meta.update(id=PID, title="The Last Lamp (one card, 8-bit)", media=[])
    (dst / "project.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    plan_doc = json.loads((dst / "plan_doc.json").read_text(encoding="utf-8"))
    plan_doc["state"] = "draft"
    for m in plan_doc["moments"]:
        m.update(status="planned", problem="", media="", preview="")
    (dst / "plan_doc.json").write_text(json.dumps(plan_doc, indent=1, ensure_ascii=False), encoding="utf-8")
plan_doc = json.loads((dst / "plan_doc.json").read_text(encoding="utf-8"))
plan_doc["state"] = "draft"
for m in plan_doc["moments"]:
    if not m.get("media"):
        m.update(status="planned", problem="")
(dst / "plan_doc.json").write_text(json.dumps(plan_doc, indent=1, ensure_ascii=False), encoding="utf-8")
th = threading.Thread(target=watch, daemon=True)
th.start()
t = time.time()
r = API.post(f"/api/projects/{PID}/plan/approve")
say("approve", r.status_code, r.text[:120])
time.sleep(10)
while API.get(f"/api/projects/{PID}").json().get("active_job"):
    time.sleep(15)
drew = time.time() - t
stop.set()
th.join(10)
plan_doc = json.loads((dst / "plan_doc.json").read_text(encoding="utf-8"))
missing = [m["id"] for m in plan_doc["moments"] if not m.get("media")]
rep = json.loads((dst / "reel_report.json").read_text(encoding="utf-8")) if (dst / "reel_report.json").exists() else {}
times = [x.get("drawn_in") for x in rep.get("slots", []) if x.get("drawn_in")]
(OUT / "samples.json").write_text(json.dumps(samples), encoding="utf-8")
say(f"drew {29 - len(missing)}/29 in {drew / 60:.1f} min; per picture {min(times or [0]):.1f}-{max(times or [0]):.1f}s; missing {missing}")
check(not missing, "every shot has its picture")

# ---- 4. render
j = API.post(f"/api/projects/{PID}/export", json={"aspects": ["9:16"], "quality": "delivery", "gpu": True, "music": "calm-01", "music_volume": 0.12, "captions": True})
j.raise_for_status()
V.wait_job(API, j.json()["id"], "render", 3600)
mp4 = Path(API.get(f"/api/projects/{PID}/exports").json()[0]["path"])
dest = OUT / "the-last-lamp-onegpu.mp4"
shutil.copy(mp4, dest)
d = V.duration(dest)
V.strip(dest, OUT / "onegpu.sheet.png", [d * (i + 0.5) / 16 for i in range(16)], 480)
say("render", dest, f"{d:.1f}s")
check(d > 60, "the video is over a minute")
say("E2E DONE")
