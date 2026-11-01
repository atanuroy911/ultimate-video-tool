"""Story QA: make videos from varied typed stories through the real Studio (zero-click path), then collect the retention score, the
director's critic score and a frame grid of each for review. Usage: python scripts/qa_stories.py [--url http://127.0.0.1:8765] [--only name,...]

Output: <scratch>/qa_stories/<name>.png (frames every few seconds) and summary.json. Needs network for the voices (edge-tts) and an AI
provider for the director (optional: the rules director runs without one)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

STORIES = [
    {"name": "bn-lion-mouse", "kind": "stick", "language": "bn", "text":
     "এক জঙ্গলে এক বিশাল সিংহ ঘুমাচ্ছিল। একটা ছোট্ট ইঁদুর খেলতে খেলতে সিংহের গায়ের উপর উঠে পড়ল। সিংহ রেগে গিয়ে ইঁদুরটাকে থাবা দিয়ে ধরে ফেলল। "
     "ইঁদুর কাঁদতে কাঁদতে বলল, আমাকে ছেড়ে দাও, একদিন আমি তোমার উপকার করব। সিংহ হেসে ইঁদুরটাকে ছেড়ে দিল। "
     "কয়েকদিন পর সিংহ শিকারির জালে আটকা পড়ল। সে জোরে গর্জন করতে লাগল। ইঁদুর গর্জন শুনে দৌড়ে এলো। "
     "সে তার ধারালো দাঁত দিয়ে জাল কেটে দিল। সিংহ মুক্ত হয়ে ইঁদুরকে ধন্যবাদ দিল। ছোট বলে কাউকে কখনো অবহেলা করতে নেই।"},
    {"name": "en-dog-ball", "kind": "cartoon", "language": "en", "text":
     "Bill and Ted were playing ball in the backyard. Ted threw the ball too high and it flew over the fence. "
     "Oh no, said Bill, that was our only ball! Their dog Max barked and ran to the gate. Jane from next door came out with the ball in her hand. "
     "Is this yours? she asked with a smile. Max jumped up and wagged his tail. Thank you, Jane! said Ted. "
     "Do you want to play with us? Jane laughed and said yes. Now four friends played in the park until the sun went down."},
    {"name": "en-compound", "kind": "explainer", "language": "en", "text":
     "Why do rich people get richer? The answer is compound interest. Imagine you save 100 dollars at 10 percent a year. "
     "After one year you have 110 dollars. The next year you earn interest on 110, not on 100. "
     "After 10 years your 100 dollars becomes 259 dollars, without adding a single cent. After 30 years it becomes 1,745 dollars. "
     "That is the power of time. Start early, even with a small amount, and let your money work while you sleep."},
    {"name": "bn-rain", "kind": "explainer", "language": "bn", "text":
     "বৃষ্টি কীভাবে হয়, জানো? সূর্যের তাপে নদী, সাগর আর পুকুরের পানি বাষ্প হয়ে উপরে উঠে যায়। একে বলে বাষ্পীভবন। "
     "উপরে ঠান্ডা বাতাসে সেই বাষ্প জমে ছোট ছোট পানির কণা তৈরি করে। অনেক কণা মিলে তৈরি হয় মেঘ। "
     "মেঘ যখন খুব ভারী হয়ে যায়, তখন পানির ফোঁটা নিচে পড়ে। এটাই বৃষ্টি। তারপর সেই পানি আবার নদীতে ফিরে যায়, আর চক্রটা চলতেই থাকে।"},
    {"name": "bn-dialogue", "kind": "stick", "language": "bn", "text":
     "রিয়া: সাম, তুমি এত চিন্তিত কেন?\nসাম: পরীক্ষা কাল, অথচ আমি কিছুই পড়িনি।\nরিয়া: এখনো সময় আছে। চলো একসাথে পড়ি।\n"
     "সাম: কিন্তু কোথা থেকে শুরু করব?\nরিয়া: সবচেয়ে কঠিন অধ্যায়টা আগে শেষ করো, তারপর সহজগুলো।\nসাম: ঠিক আছে, ধন্যবাদ রিয়া! তুমি সত্যিই ভালো বন্ধু।"},
    {"name": "en-sleep", "kind": "emoji", "language": "en", "text":
     "Five habits for better sleep. One, go to bed at the same time every night. Two, put your phone away one hour before bed. "
     "Three, keep your room cool and dark. Four, avoid coffee after 3 pm. Five, get some sunlight in the morning. "
     "Try these for one week and you will wake up feeling fresh."},
]


def call(url: str, method: str = "GET", body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"null")


def wait(base: str, pid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    seen = False
    while time.time() - t0 < timeout:
        jobs = call(base + "/api/jobs")
        mine = [j for j in (jobs if isinstance(jobs, list) else jobs.values()) if j.get("project") == pid]
        active = [j for j in mine if j["status"] in ("queued", "running")]
        if active:
            seen = True
        elif seen or mine:
            last = sorted(mine, key=lambda j: j["id"])[-1]
            return last
        time.sleep(3)
    raise TimeoutError(pid)


def grid(video: Path, out: Path, every: float = 4.0, width: int = 160) -> None:
    from PIL import Image

    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout or 0)
    ims = []
    with tempfile.TemporaryDirectory() as d:
        t = 0.5
        while t < dur and len(ims) < 24:
            f = Path(d) / f"{t:.1f}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-1", str(f)])
            if f.exists():
                ims.append(Image.open(f).copy())
            t += every
    if not ims:
        return
    cols = 8
    w, h = ims[0].size
    sheet = Image.new("RGB", (cols * (w + 4), ((len(ims) + cols - 1) // cols) * (h + 4)), "black")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
    sheet.save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "qa_stories"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8")) if (out / "summary.json").exists() else {}
    for s in STORIES:
        if a.only and s["name"] not in a.only.split(","):
            continue
        res = call(a.url + "/api/projects/from-script", "POST", {"title": "", "script": s["text"], "language": "auto", "aspect": "9:16", "theme": "auto",
                                                               "pace": "normal", "usecase": "auto", "kind": s["kind"], "start": True,
                                                               "options": {"caption_style": "auto", "music": "auto", "target_length": "auto"}})
        pid = res["project"]["id"]
        print(s["name"], "->", pid, flush=True)
        job = wait(a.url, pid)
        row = {"project": pid, "kind": s["kind"], "status": job["status"], "error": job.get("error", "")}
        pdir = root / "projects" / pid
        vids = sorted((pdir / "exports").glob("*.mp4")) if (pdir / "exports").exists() else []
        if vids:
            card = json.loads(vids[-1].with_suffix(".retention.json").read_text(encoding="utf-8")) if vids[-1].with_suffix(".retention.json").exists() else {}
            row.update({"risk": card.get("risk"), "hook": card.get("hook_s"), "worst": [w["message"] for w in card.get("worst", [])[:3]]})
            grid(vids[-1], out / f"{s['name']}.png")
        d = pdir / "director.json"
        if d.exists():
            dj = json.loads(d.read_text(encoding="utf-8"))
            row.update({"critic": dj.get("score"), "how": dj.get("how"), "notes": [i["problem"] for i in dj.get("issues", [])[:4]]})
        row["title"] = call(a.url + f"/api/projects/{pid}").get("title")
        summary[s["name"]] = row
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.exit(main())
