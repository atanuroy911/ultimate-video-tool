"""Make the acceptance videos (docs/TEST-PLAN.md section 4) through a real Studio, judge each one, and write the report.

    python scripts/run_acceptance.py --only A1,A9          # a few
    python scripts/run_acceptance.py --engine kokoro       # every script spoken by one fast local voice
    python scripts/run_acceptance.py                       # all ten with their own voices

It starts its own scratch Studio (never the owner's real one on 8765), needs the GPU machine for pictures, and writes
docs/evidence/<date>/acceptance.md plus one judge report (json) and the video per script. A video that fails a judge is a bug report, not a note.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_all_checks import SCRATCH_PORT, Scratch                     # noqa: E402
from run_reel_check import call, wait                                 # noqa: E402

OUT = ROOT / "docs" / "evidence" / date.today().isoformat() / "acceptance"


def run_one(base: str, data: Path, item: dict, engine: str | None, look: str) -> dict:
    from vt.judges import judge_video
    from vt.project import Project

    text = (ROOT / "tests" / "acceptance" / "scripts" / item["file"]).read_text(encoding="utf-8").strip()
    eng, voice = (engine, None) if engine else (item["engine"], item["voice"])
    if voice is None:
        voice = next(v["id"] for e in call(base, "/api/voices") if e["id"] == eng for v in e["voices"] if v["lang"].startswith(item["language"]))
    started = time.time()
    made = call(base, "/api/projects/from-script", {"title": f"acceptance {item['id']}", "script": text, "language": item["language"], "engine": eng, "voice": voice, "aspect": "9:16",
                                                    "options": {"look": look, "plan_review": "never"}, "start": True, "kind": "explainer"})
    pid = made["project"]["id"]
    job = wait(base, made["job"]["id"], f"{item['id']} pipeline", 3600)
    if job["status"] != "done":
        return {"id": item["id"], "stage": "pipeline", "error": job.get("error", "")[:300], "passed": False}
    job = wait(base, call(base, f"/api/projects/{pid}/export", {"aspects": ["9:16"], "quality": "looks"})["id"], f"{item['id']} export", 3600)
    if job["status"] != "done":
        return {"id": item["id"], "stage": "export", "error": job.get("error", "")[:300], "passed": False}
    project = Project(pid, data / "projects")
    video = sorted(project.exports_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)[-1]
    words = [w.model_dump() for w in project.transcript().kept()]
    sf = project.scenes()
    beats = {b.id: b for b in project.beats().beats}
    scenes = []
    for s in (sf.scenes if sf else []):
        d = s.model_dump(exclude_none=True)
        d["start"], d["end"] = beats[s.beats[0]].start, beats[s.beats[-1]].end
        d["card"] = any(getattr(e, "type", "") == "title" for e in s.elements)
        scenes.append(d)
    r = judge_video(video, words=words, scenes=scenes, target_seconds=item["expected_seconds"], kind=item["kind"], duration_tolerance=0.3)         # a sanity range for a script with no stated length
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(video, OUT / f"{item['id']}.mp4")
    (OUT / f"{item['id']}.judges.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    return {"id": item["id"], "project": pid, "seconds_to_make": round(time.time() - started), "voice": f"{eng}/{voice[:40]}", **r}


def seed_engines(data: Path) -> None:
    """The scratch Studio starts with no settings, so it would not know where the picture and language servers are. Copy the owner's engines (never a key) from the real settings."""
    real = ROOT / "settings.json"
    if not real.exists():
        return
    src = json.loads(real.read_text(encoding="utf-8"))
    engines = {k: {**v, "key": ""} for k, v in (src.get("engines") or {}).items() if k in ("ollama", "comfy") and not v.get("key")}
    mine = {k: src[k] for k in ("ollama_url", "comfy_url", "ai_provider") if k in src}
    (data / "settings.json").write_text(json.dumps({**mine, "engines": engines}), encoding="utf-8")


def rows_on_disk() -> list[dict]:
    """Every acceptance video made so far, from this run or an earlier one: a row file when the runner wrote one, else rebuilt from the judge report."""
    rows = {}
    for f in sorted(OUT.glob("A*.judges.json")):
        i = f.name.split(".")[0]
        r = json.loads(f.read_text(encoding="utf-8"))
        rows[i] = {"id": i, "passed": r.get("passed"), "failed": r.get("failed", []), "skipped": r.get("skipped", []), "verdicts": r.get("verdicts", []), "voice": "(earlier run)", "seconds_to_make": ""}
    for f in sorted(OUT.glob("A*.row.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        rows[r["id"]] = {**rows.get(r["id"], {}), **r}
    return [rows[k] for k in sorted(rows, key=lambda x: int(x[1:]))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--engine", default=None, help="speak every script with this engine's first voice in the script's language")
    ap.add_argument("--look", default="reel")
    a = ap.parse_args()
    corpus = json.loads((ROOT / "tests" / "acceptance" / "corpus.json").read_text(encoding="utf-8"))["items"]
    want = {x.strip() for x in a.only.split(",") if x.strip()}
    items = [i for i in corpus if not want or i["id"] in want]
    results: list[dict] = []
    OUT.mkdir(parents=True, exist_ok=True)
    with Scratch() as s:
        seed_engines(Path(s.dir))
        for item in items:
            try:
                results.append(run_one(f"http://127.0.0.1:{SCRATCH_PORT}", Path(s.dir), item, a.engine, a.look))
            except Exception as e:                                           # noqa: BLE001
                results.append({"id": item["id"], "stage": "runner", "error": f"{type(e).__name__}: {e}"[:300], "passed": False})
            (OUT / f"{item['id']}.row.json").write_text(json.dumps({k: v for k, v in results[-1].items()}, indent=1), encoding="utf-8")
            print(item["id"], "passed" if results[-1].get("passed") else "FAILED", flush=True)
    everything = rows_on_disk()
    lines = [f"# Acceptance run, {date.today().isoformat()}", "", "| Id | Result | Voice | Made in | Failed judges | Skipped judges |", "|---|---|---|---|---|---|"]
    for r in everything:
        lines.append(f"| {r['id']} | {'passed' if r.get('passed') else 'FAILED'} | {r.get('voice', '')} | {r.get('seconds_to_make', '')} s | {', '.join(r.get('failed', [])) or r.get('error', '') or '-'} | {', '.join(r.get('skipped', [])) or '-'} |")
    lines += ["", "Each judge's sentence is in `acceptance/<id>.judges.json`. A person fills the human checklist (docs/TEST-PLAN.md section 5) after the judges pass.", ""]
    for r in everything:
        if r.get("verdicts"):
            lines += [f"## {r['id']}", "", "| Judge | Result | Says |", "|---|---|---|"]
            lines += [f"| {v['judge']} | {({True: 'pass', False: 'FAIL', None: 'skip'})[v['passed']]} | {v['says']} |" for v in r["verdicts"]]
            lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.parent / "acceptance.md").write_text("\n".join(lines), encoding="utf-8")
    print("written", OUT.parent / "acceptance.md")
    return 0 if all(r.get("passed") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
