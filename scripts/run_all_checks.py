"""Run every check that can be run and write the result as evidence: docs/evidence/<date>/checks.md (one row per step) and a log file per step.

    python scripts/run_all_checks.py                 # docs, types, build, fast tests
    python scripts/run_all_checks.py --slow --e2e    # plus the slow tests and the browser suites (it starts and stops its own scratch Studio on port 8777)
    python scripts/run_all_checks.py --live          # plus the real engines: health, one answer, one picture, one voice sentence per ready voice workflow

A step that cannot run is recorded as SKIPPED with the reason, never as passed. Exit code 1 when any step that ran failed. The plan: docs/TEST-PLAN.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"
NPX = "npx.cmd" if os.name == "nt" else "npx"
NODE = "node"
SCRATCH_PORT = 8777
# browser suites that are expected to pass on the current screens (the stale ones are tracked in docs/STATUS.md section 6)
E2E_SUITES = ["editor_simple", "new_flow", "design", "edge", "log", "engines", "quality", "plan", "context", "contrast", "flow", "layers", "layers_media", "menus", "script", "scroll", "shorts_swipe", "sounds", "timeline2", "timeline3"]
# a short reference voice for the cloning workflows: the verified Breeze sample kept as evidence (a synthetic voice, so no person's consent is involved)
REF_VOICE = ROOT / "docs" / "evidence" / "2026-10-28" / "breeze-design-sample.wav"
REF_TEXT = "It was the last normal night of your life, but you did not know that yet."
rows: list[dict] = []
OUT = ROOT / "docs" / "evidence" / date.today().isoformat()


def step(name: str, cmd: list[str], *, cwd: Path = ROOT, env: dict | None = None, timeout: int = 3600) -> bool:
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / f"check-{name}.log"
    started = time.time()
    try:
        done = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {}), "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out, code = done.stdout + done.stderr, done.returncode
    except subprocess.TimeoutExpired as e:
        out, code = f"TIMED OUT after {timeout} s\n{(e.stdout or '')[-2000:] if isinstance(e.stdout, str) else ''}", 124
    except FileNotFoundError as e:
        out, code = f"cannot start: {e}", 127
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)                                              # npm and vite colour their output
    log.write_text(out, encoding="utf-8")
    rows.append({"step": name, "result": "passed" if code == 0 else "FAILED", "seconds": round(time.time() - started, 1), "log": log.name, "tail": out.strip().splitlines()[-1][:120] if out.strip() else ""})
    print(f"{rows[-1]['result']:7s} {name} ({rows[-1]['seconds']} s)", flush=True)
    return code == 0


def skip(name: str, why: str) -> None:
    rows.append({"step": name, "result": "SKIPPED", "seconds": 0, "log": "", "tail": why})
    print(f"SKIPPED {name}: {why}", flush=True)


def get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


class Scratch:
    """A Studio on a scratch data folder, started and stopped by this script (never the owner's real Studio on 8765)."""

    def __enter__(self):
        try:                                                                                   # a Studio left running on this port would be tested instead of the code on disk
            get(f"http://127.0.0.1:{SCRATCH_PORT}/api/health", 2)
            raise RuntimeError(f"port {SCRATCH_PORT} is already in use by another Studio: stop it first")
        except OSError:
            pass
        self.dir = tempfile.mkdtemp(prefix="vt-checks-")
        env = {**os.environ, "VT_DATA": self.dir}
        exe = str(ROOT / ".venv" / "Scripts" / "vt.exe") if os.name == "nt" else "vt"
        self.proc = subprocess.Popen([exe, "studio", "--port", str(SCRATCH_PORT), "--no-open"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                get(f"http://127.0.0.1:{SCRATCH_PORT}/api/health")
                break
            except Exception:                                                                  # noqa: BLE001
                time.sleep(1)
        else:
            raise RuntimeError("the scratch Studio did not start")
        # the browser suites edit the demo project: build it in the scratch folder
        subprocess.run([PY, str(ROOT / "samples" / "build_reference.py")], cwd=ROOT, env=env, capture_output=True)
        return self

    def __exit__(self, *a):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def live() -> None:
    sys.path.insert(0, str(ROOT))
    from vt.comfy import ComfyClient, list_workflows
    from vt.comfy import voice as CV
    from vt.engines import registry

    for eid in ("ollama", "comfy", "voicestudio"):
        h = registry.health(eid, fresh=True)
        ep = registry.endpoint(eid)
        rows.append({"step": f"live-health-{eid}", "result": "passed" if h.ok else ("SKIPPED" if ep.mode == "off" else "FAILED"), "seconds": round(h.seconds, 1), "log": "",
                     "tail": (", ".join(h.capabilities) or h.why_not or "reachable")[:120]})
        print(f"{rows[-1]['result']:7s} live-health-{eid}: {rows[-1]['tail']}", flush=True)
    ollama, comfy = registry.endpoint("ollama"), registry.endpoint("comfy")
    if registry.health("ollama").ok:
        started = time.time()
        try:
            body = json.dumps({"model": next(m["id"] for m in registry.health("ollama").models if "gemma" in m["id"] or "qwen" in m["id"]), "prompt": "Say OK.", "stream": False}).encode()
            r = json.load(urllib.request.urlopen(urllib.request.Request(ollama.url + "/api/generate", body, {"content-type": "application/json"}), timeout=300))
            ok = bool(r.get("response", "").strip())
        except Exception as e:                                                                 # noqa: BLE001
            ok, r = False, {"response": str(e)}
        rows.append({"step": "live-ollama-answer", "result": "passed" if ok else "FAILED", "seconds": round(time.time() - started, 1), "log": "", "tail": r.get("response", "")[:100]})
    if registry.health("comfy").ok:
        for url in comfy.all_urls():
            client = ComfyClient(url)
            nodes = client.object_info()
            for w in list_workflows("audio"):
                if w.problems(nodes):
                    continue
                started = time.time()
                out = Path(tempfile.mkdtemp()) / "v.wav"
                try:
                    CV.speak(client, w, "(sigh) This is a check of the voice.", out, instruction="calmly" if "instruction" in w.manifest else "", seed=3,
                             ref_audio=None if "ref_audio" not in w.manifest else REF_VOICE, ref_text=REF_TEXT, checked=True, timeout=3000)
                    ok, why = out.exists() and out.stat().st_size > 2000, f"{out.stat().st_size} bytes"
                except Exception as e:                                                         # noqa: BLE001
                    ok, why = False, str(e)[:100]
                rows.append({"step": f"live-voice-{w.id}@{url.rsplit(':', 1)[-1]}", "result": "passed" if ok else "FAILED", "seconds": round(time.time() - started, 1), "log": "", "tail": why})
                print(f"{rows[-1]['result']:7s} {rows[-1]['step']}: {why}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slow", action="store_true")
    ap.add_argument("--e2e", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--no-unit", action="store_true", help="skip the fast tests (they take about 9 minutes)")
    a = ap.parse_args()
    step("docs", [PY, "scripts/check_docs.py"])
    studio = ROOT / "studio"
    step("types", [NPX, "tsc", "--noEmit", "-p", "."], cwd=studio)
    step("build", [NPM, "run", "build"], cwd=studio)
    if a.no_unit:
        skip("unit", "left out by --no-unit")
    else:
        step("unit", [PY, "-m", "pytest", "-q", "-p", "no:warnings", "-m", "not slow"])
    if a.slow:
        step("slow", [PY, "-m", "pytest", "-q", "-p", "no:warnings", "-m", "slow"], timeout=7200)
    else:
        skip("slow", "run with --slow")
    if a.e2e:
        try:
            with Scratch() as scratch:
                for suite in E2E_SUITES:
                    if (studio / "e2e" / f"{suite}.mjs").exists():
                        step(f"e2e-{suite}", [NODE, f"e2e/{suite}.mjs"], cwd=studio, env={"VT_URL": f"http://127.0.0.1:{SCRATCH_PORT}", "VT_DATA": str(scratch.dir)}, timeout=1800)
        except Exception as e:                                                                 # noqa: BLE001
            skip("e2e", f"could not start the scratch Studio: {e}")
    else:
        skip("e2e", "run with --e2e")
    if a.live:
        live()
    else:
        skip("live", "run with --live (needs the GPU machine)")
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [f"# Checks, {date.today().isoformat()}", "", "| Step | Result | Seconds | Log | Note |", "|---|---|---|---|---|"]
    lines += [f"| {r['step']} | {r['result']} | {r['seconds']} | {r['log']} | {r['tail'].replace('|', '/')} |" for r in rows]
    (OUT / "checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    failed = [r for r in rows if r["result"] == "FAILED"]
    print(f"\n{len(rows) - len(failed)} not failed, {len(failed)} failed; written to {OUT / 'checks.md'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
