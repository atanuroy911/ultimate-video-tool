"""A matrix of real videos made by the Video Tool server installed on THIS computer, one row per kind of video. No SSH, no other machine.

    python scripts/lab/local_matrix.py list
    python scripts/lab/local_matrix.py run --director claude --smoke            # four rows first
    python scripts/lab/local_matrix.py run --director claude --all              # every row
    python scripts/lab/local_matrix.py run --director claude --rows story-lighthouse,reel-start
    python scripts/lab/local_matrix.py run --director local --rows ...          # the local AI (gemma through Ollama), when it is installed here
    python scripts/lab/local_matrix.py report [OUTDIR]                          # rebuild report.md from results.json

Each row: a script (scripts/lab/matrix/*.txt), a style (the New page's choice), a format, a language and a voice. The row is sent to
POST /api/projects/from-script, the job is followed, the video is exported, and a contact sheet and the facts are written to
E:\\UltimateVideoTool\\matrix\\<date>-<director>\\ (results.json, report.md, <row>.png). Rows already made there are skipped, so a run can be resumed.

<director> claude = Claude Code on this PC through the client helper (the server lists it as claude@<device>); local = the local AI; or any id the server lists.
Then LOOK at the sheets and the videos: the numbers cannot tell you whether a caption is cut off or a picture is wrong.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "lab" / "matrix"
API = os.environ.get("VT_API", "http://127.0.0.1:8790")
DATA = Path(os.environ.get("VT_SERVER_DATA", "E:/UltimateVideoTool/ServerData/data"))
OUT_ROOT = Path(os.environ.get("VT_MATRIX_OUT", "E:/UltimateVideoTool/matrix"))
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")

EDGE_EN = {"f": "en-US-AriaNeural", "m": "en-US-GuyNeural", "uk": "en-GB-SoniaNeural"}

# id, script file, style, aspect, language, voice engine, voice. Every style, format and language appears at least twice.
ROWS = [
    ("explainer-watch",      "watch-battery-en",   "explainer",   "9:16", "en",    "edge",   EDGE_EN["f"]),
    ("infographic-coffee",   "pour-over-en",       "infographic", "16:9", "en",    "edge",   EDGE_EN["m"]),
    ("explainer-money",      "coffee-habit-en",    "explainer",   "9:16", "en",    "edge",   EDGE_EN["m"]),
    ("story-lighthouse",     "lighthouse-cat-en",  "story",       "9:16", "en",    "edge",   EDGE_EN["uk"]),
    ("stick-monday",         "monday-stick-en",    "stick",       "9:16", "en",    "edge",   EDGE_EN["f"]),
    ("cartoon-leaves",       "leaves-cartoon-en",  "cartoon",     "16:9", "en",    "edge",   EDGE_EN["f"]),
    ("emoji-sleep",          "sleep-tips-en",      "emoji",       "9:16", "en",    "kokoro", "af_heart"),
    ("reel-start",           "start-reel-en",      "reel",        "9:16", "en",    "edge",   EDGE_EN["m"]),
    ("explainer-bikelanes",  "bike-lanes-en",      "explainer",   "16:9", "en",    "edge",   EDGE_EN["uk"]),
    ("infographic-ev",       "ev-vs-petrol-en",    "infographic", "1:1",  "en",    "edge",   EDGE_EN["f"]),
    ("story-press",          "printing-press-en",  "story",       "16:9", "en",    "edge",   EDGE_EN["m"]),
    ("stick-stretch",        "desk-stretch-en",    "stick",       "1:1",  "en",    "kokoro", "af_bella"),
    ("mixed-market",         "market-mixed-en",    "mixed",       "16:9", "en",    "edge",   EDGE_EN["f"]),
    ("auto-space",           "space-auto-en",      "auto",        "9:16", "en",    "edge",   EDGE_EN["m"]),
    ("explainer-bn-payment", "digital-payment-bn", "explainer",   "9:16", "bn",    "edge",   "bn-BD-NabanitaNeural"),
    ("story-bn-river",       "river-story-bn",     "story",       "9:16", "bn",    "edge",   "bn-BD-PradeepNeural"),
    ("infographic-bn-budget", "budget-bn",         "infographic", "16:9", "bn",    "edge",   "bn-BD-NabanitaNeural"),
    ("emoji-bn-water",       "water-tips-bn",      "emoji",       "1:1",  "bn",    "edge",   "bn-BD-PradeepNeural"),
    ("explainer-banglish",   "freelance-banglish", "explainer",   "9:16", "auto",  "auto",   "auto"),
    ("reel-banglish",        "exam-reel-banglish", "reel",        "9:16", "auto",  "auto",   "auto"),
]
SMOKE = ["story-lighthouse", "explainer-watch", "stick-monday", "explainer-bn-payment"]
GEMMA_SET = ["explainer-watch", "story-lighthouse", "stick-monday", "emoji-sleep", "infographic-coffee", "explainer-bn-payment"]


def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=120)


def ffmpeg(tool: str = "ffmpeg") -> str:
    found = shutil.which(tool)
    if found:
        return found
    hits = glob.glob(os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\{tool}.exe"))
    if hits:
        return hits[0]
    raise SystemExit(f"{tool} not found: put FFmpeg on PATH")


def pick_director(a: httpx.Client, wanted: str) -> str:
    listed = a.get("/api/directors").json()["directors"]
    if wanted == "claude":
        for d in listed:
            if d.get("kind") == "claude-client" and d.get("available"):
                return d["id"]
        raise SystemExit("Claude on this PC is not listed as ready. Open the Video Tool client (its helper connects Claude) and sign in to Claude Code.")
    if wanted == "gemma":
        wanted = "local"
    for d in listed:
        if d["id"] == wanted:
            if not d.get("available"):
                raise SystemExit(f"director {wanted} is not ready: {d.get('note')}")
            return wanted
    raise SystemExit(f"the server does not list a director '{wanted}': " + ", ".join(d["id"] for d in listed))


def wait_job(a: httpx.Client, job: str, limit: float, tag: str) -> dict:
    last, t0 = "", time.time()
    while time.time() - t0 < limit:
        j = a.get(f"/api/jobs/{job}").json()
        now = f'{j.get("status")} | {j.get("stage")} | {(j.get("msg") or "")[:90]}'
        if now != last:
            print(f"  {time.strftime('%H:%M:%S')} {tag} {now}", flush=True)
            last = now
        if j.get("status") in ("done", "error", "failed", "cancelled"):
            return j
        time.sleep(4)
    return {"status": "timeout", "error": f"not finished after {limit:.0f} s"}


def newest_export(pid: str) -> Path | None:
    files = sorted((DATA / "projects" / pid / "exports").glob("*.mp4"), key=lambda f: f.stat().st_mtime)
    return files[-1] if files else None


def probe(video: Path) -> dict:
    out = subprocess.run([ffmpeg("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
        v = next(s for s in d["streams"] if s["codec_type"] == "video")
        return {"width": v["width"], "height": v["height"], "seconds": round(float(d["format"]["duration"]), 1), "has_audio": any(s["codec_type"] == "audio" for s in d["streams"])}
    except (ValueError, StopIteration, KeyError):
        return {}


def sheet(video: Path, png: Path, seconds: float) -> None:
    every = max(1.0, round(seconds / 18, 1)) if seconds else 2
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(video), "-vf", f"fps=1/{every},scale=320:-1,tile=6x3", "-frames:v", "1", str(png)], check=False)


def make_row(a: httpx.Client, row: tuple, director: str, out: Path, quality: str, short_side: int) -> dict:
    rid, script, style, aspect, lang, engine, voice = row
    text = (SCRIPTS / f"{script}.txt").read_text(encoding="utf-8").strip()
    kind = "explainer" if style in ("auto", "reel", "story") else style                      # the same mapping as client/studio/src/pages/New.tsx
    options: dict = {"director": director, "music": "auto"}
    if style in ("reel", "story"):
        options["look"] = style
    if style == "cartoon":
        options["cartoon_template"] = "classic"
    res: dict = {"id": rid, "style": style, "aspect": aspect, "language": lang, "voice": f"{engine}/{voice}", "director_asked": director, "words": len(text.split())}
    t0 = time.time()
    r = a.post("/api/projects/from-script", json={"title": rid, "script": text, "language": lang, "engine": engine, "voice": voice, "aspect": aspect,
                                                  "theme": "auto", "kind": kind, "options": options})
    if r.status_code >= 400:
        return {**res, "status": "refused", "error": r.text[:300]}
    d = r.json()
    pid = d["project"]["id"]
    res["project"] = pid
    j = wait_job(a, d["job"]["id"], 40 * 60, rid)
    res["make_seconds"] = round(time.time() - t0)
    if j.get("status") != "done":
        return {**res, "status": "failed", "error": str(j.get("error") or j.get("status"))[:500]}
    p = a.get(f"/api/projects/{pid}").json()
    talk = a.get(f"/api/projects/{pid}/ai-talk").json().get("rows", [])
    res["director_used"] = p.get("director_used") or p.get("director")
    res["ai_conversations"] = len(talk)
    res["ai_who"] = sorted({f'{x.get("who")}/{x.get("model")}' for x in talk})
    res["ai_errors"] = [f'{x.get("stage")}: {str(x.get("error"))[:160]}' for x in talk if x.get("error")]
    res["ai_notice"] = (p.get("ai_notice") or {}).get("message")
    scenes = a.get(f"/api/projects/{pid}/scenes").json()
    res["scenes"] = len(scenes) if isinstance(scenes, list) else None
    t1 = time.time()
    e = a.post(f"/api/projects/{pid}/export", json={"aspects": [aspect], "quality": quality, "short_side": short_side})
    if e.status_code >= 400:
        return {**res, "status": "export-refused", "error": e.text[:300]}
    ej = wait_job(a, e.json()["id"], 30 * 60, rid + " export")
    res["export_seconds"] = round(time.time() - t1)
    if ej.get("status") != "done":
        return {**res, "status": "export-failed", "error": str(ej.get("error") or ej.get("status"))[:500]}
    video = newest_export(pid)
    if not video:
        return {**res, "status": "export-missing", "error": "no mp4 in the project's exports folder"}
    facts = probe(video)
    res.update(status="made", video=str(video), **facts)
    retention = video.with_suffix(".retention.json")
    if retention.exists():
        try:
            res["retention"] = json.loads(retention.read_text(encoding="utf-8"))
        except ValueError:
            pass
    sheet(video, out / f"{rid}.png", facts.get("seconds", 0))
    return res


def write_report(out: Path) -> None:
    results = json.loads((out / "results.json").read_text(encoding="utf-8")) if (out / "results.json").exists() else []
    lines = [f"# Matrix {out.name}", "", f"{sum(r.get('status') == 'made' for r in results)} made, {sum(r.get('status') != 'made' for r in results)} not made, of {len(results)} rows.", "",
             "| row | style | format | lang | director used | make | export | length | scenes | AI errors | status |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append("| {id} | {style} | {aspect} | {language} | {du} | {ms}s | {es}s | {sec}s | {sc} | {err} | {st} |".format(
            id=r["id"], style=r["style"], aspect=r["aspect"], language=r["language"], du=json.dumps(r.get("director_used"), ensure_ascii=False)[:40] if r.get("director_used") else "-",
            ms=r.get("make_seconds", "-"), es=r.get("export_seconds", "-"), sec=r.get("seconds", "-"), sc=r.get("scenes", "-"), err=len(r.get("ai_errors") or []),
            st=r["status"] + (": " + r["error"][:80].replace("|", "/") if r.get("error") else "")))
    lines += ["", "## Details", ""]
    for r in results:
        lines.append(f"### {r['id']}  ({r['status']})")
        for k in ("project", "video", "ai_who", "ai_notice", "ai_errors", "retention"):
            if r.get(k):
                lines.append(f"- {k}: `{json.dumps(r[k], ensure_ascii=False)[:600]}`")
        lines.append(f"- sheet: `{r['id']}.png`")
        lines.append("")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run(x: argparse.Namespace) -> None:
    a = client()
    director = pick_director(a, x.director)
    ids = [r[0] for r in ROWS]
    chosen = ids if x.all else SMOKE if x.smoke else GEMMA_SET if x.gemma_set else [s.strip() for s in (x.rows or "").split(",") if s.strip()]
    if not chosen:
        raise SystemExit("choose rows: --smoke, --all, --gemma-set or --rows a,b")
    unknown = [c for c in chosen if c not in ids]
    if unknown:
        raise SystemExit("unknown rows: " + ", ".join(unknown))
    out = Path(x.out) if x.out else OUT_ROOT / f"{date.today():%Y-%m-%d}-{x.director}"
    out.mkdir(parents=True, exist_ok=True)
    file = out / "results.json"
    results = json.loads(file.read_text(encoding="utf-8")) if file.exists() else []
    done = {r["id"] for r in results if r.get("status") == "made"}
    print(f"director {director}; {len(chosen)} rows; output {out}")
    for row in ROWS:
        if row[0] not in chosen or (row[0] in done and not x.force):
            continue
        print(f"== {row[0]}  {row[2]} {row[3]} {row[4]}", flush=True)
        res = make_row(a, row, director, out, x.quality, x.short_side)
        results = [r for r in results if r["id"] != row[0]] + [res]
        file.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        write_report(out)
        print(f"   -> {res['status']}" + (f": {res.get('error')}" if res.get("error") else f" in {res.get('make_seconds')} s + {res.get('export_seconds')} s"), flush=True)
    write_report(out)
    print("report:", out / "report.md")


def main() -> None:
    top = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = top.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("run")
    p.add_argument("--director", default="claude")
    p.add_argument("--rows")
    p.add_argument("--all", action="store_true")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--gemma-set", action="store_true", help="the six rows used for the comparison with the local AI")
    p.add_argument("--force", action="store_true", help="make rows again even when already made")
    p.add_argument("--out")
    p.add_argument("--quality", default="looks", choices=["draft", "looks", "delivery"])
    p.add_argument("--short-side", type=int, default=720)
    r = sub.add_parser("report")
    r.add_argument("outdir", nargs="?")
    x = top.parse_args()
    if x.cmd == "list":
        for row in ROWS:
            print("  {:22} {:11} {:5} {:5} {:7} {}".format(row[0], row[2], row[3], row[4], row[5], row[1]))
        return
    if x.cmd == "report":
        write_report(Path(x.outdir) if x.outdir else sorted(OUT_ROOT.iterdir())[-1])
        return
    run(x)


if __name__ == "__main__":
    main()
