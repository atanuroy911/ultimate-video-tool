"""Run the project's test suites and keep the output, so every "done" in docs/STATUS.md has a log behind it.

    python scripts/collect_evidence.py fast                       # pytest -m "not slow"
    python scripts/collect_evidence.py slow                       # pytest -m slow (renders frames, runs the speech model)
    python scripts/collect_evidence.py e2e --url http://127.0.0.1:8777 [--only editor,dashboard] [--long]
    python scripts/collect_evidence.py docs                       # the docs checker

Output goes to docs/evidence/<YYYY-MM-DD>/ : <suite>.log, pytest junit XML, and summary.json / summary.md (appended to on every run).
The browser suites need a running Studio on a SCRATCH data folder (they edit the projects they run on):
    VT_DATA=<scratch> .venv\\Scripts\\vt studio --port 8777 --no-open
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "client" / "studio"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv" / "Scripts" / "python.exe").exists() else sys.executable
EVIDENCE = ROOT / "docs" / "evidence" / date.today().isoformat()

# name -> (script, extra env, needs, seconds allowed)
#   needs: "" nothing special, "stick" a stick-figure project, "comfy" a project with generated clips, "long" renders or speech models
E2E = {
    "editor": ("editor.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "stick": ("stick.mjs", {"VT_PROJECT": "{stick}"}, "stick", 300),
    "dashboard": ("dashboard.mjs", {}, "", 300),
    "menus": ("menus.mjs", {}, "", 200),
    "flow": ("flow.mjs", {}, "", 300),
    "comfy": ("comfy.mjs", {"VT_PROJECT": "{comfy}"}, "comfy", 300),
    "timeline2": ("timeline2.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "timeline3": ("timeline3.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "layers": ("layers.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "layers_media": ("layers_media.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "script": ("script.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "scroll": ("scroll.mjs", {"VT_PROJECT": "reference"}, "", 200),
    "sounds": ("sounds.mjs", {"VT_PROJECT": "reference"}, "", 200),
    "context": ("context.mjs", {"VT_PROJECT": "reference"}, "", 200),
    "new_flow": ("new_flow.mjs", {}, "", 200),
    "edge": ("edge.mjs", {"VT_PROJECT": "reference"}, "", 400),
    "design": ("design.mjs", {}, "", 300),
    "contrast": ("contrast.mjs", {"VT_PROJECT": "reference"}, "", 300),
    "crawl": ("crawl.mjs", {"VT_PROJECT": "reference"}, "", 600),
    "shorts_swipe": ("shorts_swipe.mjs", {}, "", 200),
    "retention": ("retention.mjs", {"VT_PROJECT": "reference"}, "long", 600),
    "export": ("export.mjs", {"VT_PROJECT": "reference"}, "long", 900),
    "simple": ("simple.mjs", {}, "long", 1500),
    "journey": ("journey.mjs", {}, "long", 1500),
}


def run(cmd: list[str], log: Path, cwd: Path, env_extra: dict[str, str], timeout: int) -> tuple[int, float, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **env_extra}
    t0 = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as out:
        out.write(f"$ {' '.join(cmd)}\n# cwd {cwd}\n# started {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        out.flush()
        try:
            r = subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
            code = r.returncode
        except subprocess.TimeoutExpired:
            out.write(f"\n# TIMED OUT after {timeout} s\n")
            code = 124
        out.write(f"\n# exit {code} in {time.time() - t0:.0f} s\n")
    tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:])
    return code, time.time() - t0, tail


def record(entry: dict) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / "summary.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows = [r for r in rows if r["suite"] != entry["suite"]] + [entry]
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = ["# Test evidence", "", f"Collected {EVIDENCE.name} by `scripts/collect_evidence.py`. Logs sit next to this file.", "",
             "| Suite | Result | Seconds | Log |", "|---|---|---:|---|"]
    for r in sorted(rows, key=lambda r: r["suite"]):
        lines.append(f"| {r['suite']} | {'PASS' if r['exit'] == 0 else 'FAIL (exit ' + str(r['exit']) + ')'} | {r['seconds']:.0f} | `{r['log']}` |")
    (EVIDENCE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pytest(name: str, marker: str) -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    log = EVIDENCE / f"{name}.log"
    code, sec, tail = run([PY, "-m", "pytest", "-q", "-p", "no:warnings", "-m", marker, f"--junitxml={EVIDENCE / (name + '.xml')}"], log, ROOT, {}, 3600)
    return {"suite": f"pytest-{name}", "exit": code, "seconds": sec, "log": str(log.relative_to(ROOT)).replace("\\", "/"), "tail": tail}


def e2e(args) -> list[dict]:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    wanted = args.only.split(",") if args.only else [n for n, v in E2E.items() if args.long or v[2] != "long"]
    results = []
    for name in wanted:
        script, env, needs, secs = E2E[name]
        env = {k: v.format(stick=args.stick, comfy=args.comfy) for k, v in env.items()}
        env["VT_URL"] = args.url
        log = EVIDENCE / f"e2e-{name}.log"
        out_dir = str(EVIDENCE / "shots")
        Path(out_dir).mkdir(exist_ok=True)
        cmd = ["node", f"e2e/{script}"] + ([out_dir] if name in ("flow", "dashboard", "menus", "comfy") else [])
        code, sec, tail = run(cmd, log, STUDIO, env, secs)
        entry = {"suite": f"e2e-{name}", "exit": code, "seconds": sec, "log": str(log.relative_to(ROOT)).replace("\\", "/"), "tail": tail}
        record(entry)
        results.append(entry)
        print(f"{'PASS' if code == 0 else 'FAIL'}  e2e-{name}  {sec:.0f}s", flush=True)
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["fast", "slow", "e2e", "docs"])
    ap.add_argument("--url", default="http://127.0.0.1:8777")
    ap.add_argument("--only", default="")
    ap.add_argument("--long", action="store_true", help="include suites that render video or load the speech model")
    ap.add_argument("--stick", default="2026-10-23-saving-money-is-simple", help="a project with a stick-figure plan")
    ap.add_argument("--comfy", default="2026-10-24-saving-money-is-simple", help="a project with generated clips")
    args = ap.parse_args()
    if args.what == "fast":
        entry = pytest("fast", "not slow")
        record(entry)
        print(entry["tail"])
    elif args.what == "slow":
        entry = pytest("slow", "slow")
        record(entry)
        print(entry["tail"])
    elif args.what == "e2e":
        e2e(args)
    else:
        sys.exit(subprocess.call([PY, str(ROOT / "scripts" / "check_docs.py")]))


if __name__ == "__main__":
    main()
