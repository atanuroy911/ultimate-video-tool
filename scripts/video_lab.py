"""The video lab: make every kind of video through the running Studio, render it, and judge it by retention.

    python scripts/video_lab.py --url http://127.0.0.1:8771 --out "C:/Users/Roy/Videos/Video Tool Lab/round-01"
    python scripts/video_lab.py ... --only stick,emoji          # a few cases again
    python scripts/video_lab.py --compare round-01 round-02     # what changed between two rounds

Each case is a real project (a typed script spoken by a voice, or a real recording) that goes through the whole pipeline. For every MP4 it keeps:
the retention scorecard (vt/retention.py), the automatic judges (vt/judges.py), loudness, a contact sheet (one frame every ~2 s), and the
first-three-seconds strip (what decides whether a viewer stays). `report.md` ranks the cases by the retention score and lists the worst moments.
Nothing is mocked: every number comes from the file the Studio produced.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt.util import find_tool  # noqa: E402

EN_SLEEP = ("Most people think sleep is lost time. It is the opposite. While you sleep, your brain washes away the waste it built up all day. "
            "Skip one night and your focus drops by a third. Skip a week and your body handles sugar like someone much older. "
            "The fix is simple: same bedtime, a dark room, and no screen for the last thirty minutes. Try it for seven days and watch what happens.")
EN_STORY = ("Ten years ago, a boy in Dhaka sold tea at a bus stop. Every day he watched the same man buy a cup and read the business news. "
            "One morning the boy asked him what the numbers meant. The man laughed, then sat down and explained compound interest on a paper napkin. "
            "The boy saved one taka a day. Today he runs three shops. He still keeps that napkin in his wallet.")
EN_PRODUCT = ("This is the smallest power bank we have ever made. It fits in your coin pocket, yet it charges a phone from zero to half in twenty minutes. "
              "The case is recycled aluminium, so it survives drops. There are no cables to forget: the plug folds out of the side. "
              "It costs less than a lunch for two. Tap the link and get yours before Friday.")
EN_DATA = ("Bangladesh exported forty seven billion dollars of goods last year. Eighty four percent of that was clothing. "
           "Ten years ago clothing was seventy eight percent, so the country now depends on it even more. "
           "Electronics grew five times in the same period, but they are still under two percent. One industry carries the whole economy.")
EN_DEBATE = ("Should students use AI to write their homework? Supporters say it is just a new calculator: it frees time for thinking. "
             "Critics say writing is thinking, and skipping it skips the learning. The research so far points in one direction: "
             "students who draft first and ask the AI to criticise learn the most. Those who let it write learn the least. So the question is not whether, but when.")
BN_SCRIPT = ("আপনি কি জানেন, প্রতিদিন মাত্র দশ মিনিট হাঁটলে আপনার আয়ু বাড়তে পারে? গবেষণা বলছে, যারা নিয়মিত হাঁটেন তাদের হৃদরোগের ঝুঁকি "
             "প্রায় ত্রিশ শতাংশ কম। হাঁটা মন ভালো রাখে, ঘুম গভীর করে, আর ওজন নিয়ন্ত্রণে রাখে। আজ থেকেই শুরু করুন, লিফট নয়, সিঁড়ি ব্যবহার করুন।")

# id, source (script text or a recording path), language, kind, use case, aspect
CASES = [
    ("explainer-general", EN_SLEEP, "en", "explainer", "general", "9:16"),
    ("explainer-education-bn", BN_SCRIPT, "bn", "explainer", "education", "9:16"),
    ("recording-bn", "samples/audio/bn_plain.mp3", "bn", "explainer", "auto", "9:16"),
    ("recording-banglish-square", "samples/audio/banglish.mp3", "bn", "explainer", "auto", "1:1"),
    ("story-cartoon", EN_STORY, "en", "cartoon", "story", "9:16"),
    ("product", EN_PRODUCT, "en", "explainer", "product", "9:16"),
    ("infographic", EN_DATA, "en", "infographic", "education", "9:16"),
    ("stick", EN_SLEEP, "en", "stick", "auto", "9:16"),
    ("emoji", EN_STORY, "en", "emoji", "auto", "9:16"),
    ("mixed-wide", EN_DEBATE, "en", "mixed", "discussion", "16:9"),
]
VOICES = {"en": ("edge", "en-US-AndrewNeural"), "bn": ("edge", "bn-BD-NabanitaNeural")}
KINDS = ("explainer", "infographic", "stick", "emoji", "cartoon", "mixed")
USECASES = ("general", "education", "story", "product", "discussion")
ASPECTS = ("9:16", "16:9", "1:1")
SCRIPT_FOR = {"general": EN_SLEEP, "education": EN_DATA, "story": EN_STORY, "product": EN_PRODUCT, "discussion": EN_DEBATE}


def matrix_cases() -> list[tuple]:
    """One video per look (66 film styles + the 3 house themes). Kinds, use cases, shapes, languages and sources rotate so that every
    kind meets every shape and every use case, and both languages and both sources (typed script, real recording) appear: a covering
    design instead of 25,000 renders."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from vt import styles

    looks = ["paper", "minimal", "dark-neon"] + [f"style-{s['slug']}" for s in styles.index()]
    out = []
    for i, look in enumerate(looks):
        kind, usecase, aspect = KINDS[i % 6], USECASES[(i // 6) % 5], ASPECTS[(i + i // 6) % 3]
        if i % 7 == 3:
            src, lang = ("samples/audio/bn_plain.mp3" if i % 2 else "samples/audio/banglish.mp3"), "bn"
        elif i % 4 == 1:
            src, lang = BN_SCRIPT, "bn"
        else:
            src, lang = SCRIPT_FOR[usecase], "en"
        out.append((f"{i + 1:02d}-{look.removeprefix('style-')}-{kind}-{usecase}-{aspect.replace(':', 'x')}-{lang}", src, lang, kind, usecase, aspect, look))
    return out


def wait_job(c: httpx.Client, job_id: str, label: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error", "cancelled"):
            if j["status"] != "done":
                raise RuntimeError(f"{label}: {j['status']} {str(j.get('error', ''))[:400]}")
            return j
        time.sleep(2)
    raise TimeoutError(label)


def wait_idle(c: httpx.Client, pid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = c.get(f"/api/projects/{pid}").json()
        if not st.get("active_job") and st["status"] not in ("processing", "queued"):
            return st
        time.sleep(2)
    raise TimeoutError(pid)


def ff(*args: str) -> str:
    r = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stderr


def duration(path: Path) -> float:
    r = subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def loudness(path: Path) -> dict:
    import re

    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", ff("-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"), re.S)
    try:
        j = json.loads(m.group(0))
        return {"lufs": float(j["input_i"]), "peak_db": float(j["input_tp"])}
    except Exception:                                                                   # noqa: BLE001
        return {}


def strip(video: Path, out: Path, times: list[float], height: int = 640) -> None:
    """Frames at the given times side by side (a contact sheet)."""
    from PIL import Image

    tmp = out.parent / f"_{out.stem}"
    tmp.mkdir(exist_ok=True)
    ims = []
    for i, t in enumerate(times):
        f = tmp / f"{i}.png"
        ff("-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale=-2:{height}", str(f))
        if f.exists():
            ims.append(Image.open(f).copy())
            f.unlink()
    tmp.rmdir()
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), 8)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)


def make(c: httpx.Client, case: tuple, out: Path, quality: str) -> dict:
    cid, src, lang, kind, usecase, aspect = case[:6]
    theme = case[6] if len(case) > 6 else "auto"
    t0 = time.time()
    if Path(src).suffix in (".mp3", ".wav") and Path(src).exists():
        with open(src, "rb") as f:
            r = c.post("/api/projects", files={"audio": (Path(src).name, f, "audio/mpeg")},
                       data={"title": f"Lab {cid}", "language": lang, "aspect": aspect, "theme": theme, "usecase": usecase, "kind": kind})
    else:
        engine, voice = VOICES[lang]
        r = c.post("/api/projects/from-script", json={"title": f"Lab {cid}", "script": src, "language": lang, "engine": engine, "voice": voice,
                                                       "aspect": aspect, "theme": theme, "usecase": usecase, "kind": kind})
    r.raise_for_status()
    body = r.json()
    pid = body["project"]["id"]
    if body.get("job"):
        wait_job(c, body["job"]["id"], f"{cid}: make")
    wait_idle(c, pid)
    made_s = time.time() - t0
    j = c.post(f"/api/projects/{pid}/export", json={"aspects": [aspect], "quality": quality, "gpu": True, "music": "project", "captions": True})
    j.raise_for_status()
    wait_job(c, j.json()["id"], f"{cid}: render", 2400)
    files = c.get(f"/api/projects/{pid}/exports").json()
    mp4 = Path(files[0]["path"])
    dest = out / f"{cid}.mp4"
    dest.write_bytes(mp4.read_bytes())
    card = json.loads(mp4.with_suffix(".retention.json").read_text(encoding="utf-8")) if mp4.with_suffix(".retention.json").exists() else {}
    review = {}
    try:
        review = c.post(f"/api/projects/{pid}/judge").json()
    except Exception:                                                                   # noqa: BLE001
        pass
    d = duration(dest)
    strip(dest, out / f"{cid}.sheet.png", [d * (i + 0.5) / 16 for i in range(16)], 480)
    strip(dest, out / f"{cid}.hook.png", [0.0, 0.5, 1.0, 1.5, 2.0, 3.0], 640)
    plan = c.get(f"/api/projects/{pid}/scenes").json().get("plan", {}).get("scenes", [])
    row = {"case": cid, "project": pid, "theme": theme, "kind": kind, "usecase": usecase, "aspect": aspect, "lang": lang, "duration": round(d, 1),
           "scenes": len(plan), "seconds_per_scene": round(d / max(1, len(plan)), 2), "make_s": round(made_s), "render_s": round(time.time() - t0 - made_s),
           "score": card.get("score"), "hook_s": card.get("hook_s"), "longest_gap_s": card.get("longest_gap_s"), "gaps_over_target": card.get("gaps_over_target"),
           "empty_longest_s": card.get("empty_longest_s"), "motion": card.get("motion"), "fast_captions": card.get("fast_captions"),
           "points_lost": card.get("points_lost"), "worst": card.get("worst", [])[:3], **loudness(dest),
           "judges": {v.get("judge"): v.get("passed") for v in (review.get("verdicts") or [])} if isinstance(review, dict) else {}}
    (out / f"{cid}.json").write_text(json.dumps({"row": row, "card": card, "review": review}, indent=2, ensure_ascii=False), encoding="utf-8")
    return row


def report(rows: list[dict], out: Path) -> None:
    rows = sorted(rows, key=lambda r: -(r.get("score") or 0))
    lines = ["# Video lab report", "", f"{len(rows)} videos. Score = 100 minus the points lost on the retention scorecard (vt/retention.py).", "",
             "| Case | Kind | Shape | Length | Score | Hook | Longest still | Empty | Motion | s/scene | LUFS |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['case']} | failed: {r['error'][:80]} |||||||||| ")
            continue
        lines.append(f"| {r['case']} | {r['kind']} | {r['aspect']} | {r['duration']} s | **{r['score']}** | {r['hook_s']} s | {r['longest_gap_s']} s | "
                     f"{r['empty_longest_s']} s | {r['motion']} | {r['seconds_per_scene']} | {r.get('lufs', '')} |")
    lines += ["", "## Worst moments", ""]
    for r in rows:
        for m in r.get("worst", []):
            lines.append(f"- **{r['case']}** {m['t0']}-{m['t1']} s: {m['message']}")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def compare(a: Path, b: Path) -> None:
    ra = {r["case"]: r for r in json.loads((a / "report.json").read_text(encoding="utf-8"))}
    rb = {r["case"]: r for r in json.loads((b / "report.json").read_text(encoding="utf-8"))}
    print(f"{'case':28} {'score':>13} {'hook':>11} {'longest still':>15} {'empty':>11}")
    for k in sorted(set(ra) | set(rb)):
        x, y = ra.get(k, {}), rb.get(k, {})
        f = lambda key: f"{x.get(key)} -> {y.get(key)}"                                      # noqa: E731
        print(f"{k:28} {f('score'):>13} {f('hook_s'):>11} {f('longest_gap_s'):>15} {f('empty_longest_s'):>11}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8771")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--quality", default="looks")
    ap.add_argument("--compare", nargs=2, default=None)
    ap.add_argument("--matrix", action="store_true", help="every look with rotating kinds, use cases, shapes, languages and sources (69 videos)")
    a = ap.parse_args()
    if a.compare:
        compare(Path(a.compare[0]), Path(a.compare[1]))
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(base_url=a.url, timeout=300)
    rows = []
    prev = out / "report.json"
    if prev.exists():
        rows = [r for r in json.loads(prev.read_text(encoding="utf-8")) if not a.only or r["case"] not in a.only.split(",")]
    for case in (matrix_cases() if a.matrix else CASES):
        if a.only and case[0] not in a.only.split(","):
            continue
        if not a.only and any(r["case"] == case[0] and not r.get("error") for r in rows):
            continue                                                                    # resumable: done cases are kept
        print(f"== {case[0]}", flush=True)
        try:
            row = make(c, case, out, a.quality)
            print(json.dumps({k: row[k] for k in ("case", "duration", "scenes", "score", "hook_s", "longest_gap_s", "empty_longest_s", "make_s", "render_s")}), flush=True)
        except Exception as e:                                                          # noqa: BLE001
            row = {"case": case[0], "error": str(e)}
            print("   failed:", str(e)[:300], flush=True)
        rows = [r for r in rows if r["case"] != case[0]] + [row]
        report(rows, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
