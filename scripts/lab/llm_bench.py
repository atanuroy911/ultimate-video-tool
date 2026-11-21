"""Which local AI model fits THIS computer's graphics card, measured, not guessed. It replays real calls the Video Tool server made to the local AI
(recorded in each project's ai_talk.jsonl: the frame reviews with their pictures, the planning and describing calls) on each candidate model, and records:

  - whether the whole model and its context stay on the card (Ollama's /api/ps: size_vram against size), at each context size the app asks for;
  - the graphics memory in use (nvidia-smi), reading and writing speed, seconds per call;
  - whether the answer is valid JSON, and the answer itself, to judge by reading.

    python scripts/lab/llm_bench.py pull gemma3:4b qwen3.5:4b gemma4:e2b
    python scripts/lab/llm_bench.py fit  gemma3:4b qwen3.5:4b --ctx 8192,16384,32768 --kv f16,q8_0
    python scripts/lab/llm_bench.py run  gemma3:4b qwen3.5:4b --kv q8_0 --calls 24
    python scripts/lab/llm_bench.py report

It starts its own Ollama on port 11500 (the server's own copy of the program and its model folder), so the server's settings are not touched. Close the
server's other GPU work first: the numbers are only true on a quiet card. Output: E:\\UltimateVideoTool\\llm-bench\\<date>\\.
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import random
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import httpx

DATA = Path(os.environ.get("VT_SERVER_DATA", "E:/UltimateVideoTool/ServerData/data"))
EXE = Path(os.environ.get("VT_OLLAMA_EXE", str(DATA / "engines" / "ollama" / "ollama.exe")))
MODELS = Path(os.environ.get("VT_OLLAMA_MODELS", str(DATA / "models" / "ollama")))
OUT = Path(os.environ.get("VT_BENCH_OUT", "E:/UltimateVideoTool/llm-bench")) / f"{date.today():%Y-%m-%d}"
PORT = 11500
BASE = f"http://127.0.0.1:{PORT}"
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")


def context_for(prompt_chars: int, answer_tokens: int = 2048) -> int:
    """The same sum as vt/ai/providers.py context_for: Bangla and JSON run at about 2.5 characters a token."""
    need = int(prompt_chars / 2.5) + answer_tokens + 512
    return min(65536, max(16384, (need // 4096 + 1) * 4096))


class Ollama:
    """Our own Ollama on PORT with the given cache settings; stopped on exit."""

    def __init__(self, kv: str = "f16", fa: str = "1"):
        self.kv, self.fa, self.proc = kv, fa, None

    def __enter__(self):
        env = {**os.environ, "OLLAMA_HOST": f"127.0.0.1:{PORT}", "OLLAMA_MODELS": str(MODELS), "OLLAMA_KEEP_ALIVE": "5m",
               "OLLAMA_FLASH_ATTENTION": self.fa, "OLLAMA_KV_CACHE_TYPE": self.kv, "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1"}
        env.pop("ELECTRON_RUN_AS_NODE", None)
        self.proc = subprocess.Popen([str(EXE), "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        for _ in range(80):
            try:
                httpx.get(BASE + "/api/version", timeout=1)
                return self
            except httpx.HTTPError:
                time.sleep(0.25)
        raise SystemExit("our Ollama did not start")

    def __exit__(self, *a):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def unload_all() -> None:
    try:
        for m in httpx.get(BASE + "/api/ps", timeout=5).json().get("models", []):
            httpx.post(BASE + "/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
    except httpx.HTTPError:
        pass
    time.sleep(1.5)


def card_used_mb() -> int:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    return int(out.split()[0]) if out.strip() else 0


def placement(model: str) -> dict:
    for m in httpx.get(BASE + "/api/ps", timeout=5).json().get("models", []):
        if m["name"].split(":")[0] == model.split(":")[0]:
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            return {"size_gb": round(size / 1e9, 2), "vram_gb": round(vram / 1e9, 2), "on_card": round(vram / size, 3) if size else 0.0,
                    "context": m.get("context_length")}
    return {}


def pull(models: list[str]) -> None:
    with Ollama():
        for name in models:
            print("pulling", name, flush=True)
            last = ""
            with httpx.stream("POST", BASE + "/api/pull", json={"model": name}, timeout=None) as r:
                for line in r.iter_lines():
                    if not line:
                        continue
                    d = json.loads(line)
                    msg = d.get("status", "")
                    if d.get("total"):
                        msg += f" {100 * d.get('completed', 0) // d['total']}%"
                    if msg != last and (not d.get("total") or msg.endswith("0%")):
                        print("  ", msg, flush=True)
                        last = msg
                    if d.get("error"):
                        raise SystemExit(d["error"])
            print("  done", flush=True)


def fit(models: list[str], ctxs: list[int], kvs: list[str]) -> list[dict]:
    rows = []
    for kv in kvs:
        with Ollama(kv=kv):
            for model in models:
                for ctx in ctxs:
                    unload_all()
                    base = card_used_mb()
                    t0 = time.time()
                    r = httpx.post(BASE + "/api/generate", json={"model": model, "prompt": "Say OK.", "stream": False, "keep_alive": "2m",
                                                                 "options": {"num_ctx": ctx, "num_predict": 4}}, timeout=600)
                    row = {"model": model, "kv": kv, "ctx": ctx, "load_s": round(time.time() - t0, 1), "card_before_mb": base}
                    if r.status_code >= 400:
                        row["error"] = r.text[:200]
                    else:
                        row.update(placement(model))
                        row["card_after_mb"] = card_used_mb()
                    print(json.dumps(row), flush=True)
                    rows.append(row)
            unload_all()
    save("fit.json", rows)
    return rows


def recorded_calls(limit: int) -> list[dict]:
    """Real calls the server made to the local AI, with their pictures: frame reviews (compose) and planning and describing calls (plan)."""
    calls = []
    for f in sorted(glob.glob(str(DATA / "projects" / "*" / "ai_talk.jsonl"))):
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("who") != "ollama" or not r.get("prompt") or r.get("error"):
                continue
            folder = Path(f).parent / "ai-talk-images"                    # the pictures are kept by name in the project's ai-talk-images folder
            images = [str(folder / p) for p in (r.get("image_files") or []) if (folder / p).exists()]
            calls.append({"project": Path(f).parent.name, "stage": r.get("stage"), "system": r.get("system") or "", "prompt": r["prompt"],
                          "images": images, "schema": r.get("schema"), "recorded_answer": r.get("answer"), "recorded_model": r.get("model"), "recorded_s": r.get("seconds")})
    random.Random(7).shuffle(calls)
    plans = sorted([c for c in calls if c["stage"] != "compose"], key=lambda c: -len(c["prompt"]))[:max(2, limit // 4)]
    composes = [c for c in calls if c["stage"] == "compose"][:limit - len(plans)]
    return plans + composes


def run(models: list[str], kv: str, limit: int) -> list[dict]:
    calls = recorded_calls(limit)
    print(f"{len(calls)} recorded calls: {sum(c['stage'] == 'compose' for c in calls)} frame reviews with pictures, the rest planning", flush=True)
    rows = []
    with Ollama(kv=kv):
        for model in models:
            unload_all()
            for i, c in enumerate(calls):
                msg = {"role": "user", "content": c["prompt"]}
                if c["images"]:
                    msg["images"] = [base64.b64encode(Path(p).read_bytes()).decode() for p in c["images"][:2]]
                ctx = context_for(len(c["system"]) + len(c["prompt"]))
                body = {"model": model, "messages": ([{"role": "system", "content": c["system"]}] if c["system"] else []) + [msg], "stream": False,
                        "format": c.get("schema") or "json", "think": False, "keep_alive": "5m", "options": {"temperature": 0.2, "num_ctx": ctx, "num_predict": 2048}}
                t0 = time.time()
                try:
                    r = httpx.post(BASE + "/api/chat", json=body, timeout=900)
                    d = r.json()
                    answer = (d.get("message") or {}).get("content", "")
                    err = d.get("error", "")
                except (httpx.HTTPError, ValueError) as e:
                    d, answer, err = {}, "", f"{type(e).__name__}: {e}"
                try:
                    json.loads(answer)
                    valid = True
                except ValueError:
                    valid = False
                row = {"model": model, "kv": kv, "i": i, "project": c["project"], "stage": c["stage"], "pictures": len(c["images"]), "ctx": ctx,
                       "seconds": round(time.time() - t0, 1), "prompt_tokens": d.get("prompt_eval_count"), "answer_tokens": d.get("eval_count"),
                       "read_tps": round(d["prompt_eval_count"] / (d["prompt_eval_duration"] / 1e9), 1) if d.get("prompt_eval_duration") else None,
                       "write_tps": round(d["eval_count"] / (d["eval_duration"] / 1e9), 1) if d.get("eval_duration") else None,
                       "done_reason": d.get("done_reason"), "valid_json": valid, "error": err[:200], **placement(model), "card_mb": card_used_mb(),
                       "answer": answer[:3000], "recorded_answer": str(c["recorded_answer"])[:1500], "prompt_head": c["prompt"][:600]}
                print(f"{model:14} {c['stage']:8} pics={row['pictures']} ctx={ctx:6} {row['seconds']:6}s on_card={row.get('on_card')} "
                      f"read={row['read_tps']} write={row['write_tps']} json={valid} {err[:60]}", flush=True)
                rows.append(row)
            unload_all()
    save(f"run-{kv}.json", rows)
    return rows


def save(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    old = []
    if (OUT / name).exists():
        old = json.loads((OUT / name).read_text(encoding="utf-8"))
    keys = {(r["model"], r.get("kv"), r.get("ctx"), r.get("i")) for r in rows}
    merged = [r for r in old if (r["model"], r.get("kv"), r.get("ctx"), r.get("i")) not in keys] + rows
    (OUT / name).write_text(json.dumps(merged, indent=1, ensure_ascii=False), encoding="utf-8")


def report() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [f"# Local AI on this card ({date.today()})", ""]
    if (OUT / "fit.json").exists():
        lines += ["## Does it stay on the card?", "", "| model | cache | context | on the card | model + context GB | card used MB | load s |", "|---|---|---:|---:|---:|---:|---:|"]
        for r in json.loads((OUT / "fit.json").read_text(encoding="utf-8")):
            lines.append(f"| {r['model']} | {r['kv']} | {r['ctx']} | {int(100 * r.get('on_card', 0))}% | {r.get('size_gb', '-')} | {r.get('card_after_mb', '-')} | {r['load_s']} |"
                         + (f" {r['error']}" if r.get("error") else ""))
    for f in sorted(OUT.glob("run-*.json")):
        rows = json.loads(f.read_text(encoding="utf-8"))
        lines += ["", f"## Real calls ({f.stem})", "", "| model | calls | valid JSON | all on card | median s (frame review) | median s (planning) | read tok/s | write tok/s |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for model in dict.fromkeys(r["model"] for r in rows):
            mine = [r for r in rows if r["model"] == model]
            med = lambda xs: sorted(xs)[len(xs) // 2] if xs else "-"
            lines.append(f"| {model} | {len(mine)} | {sum(r['valid_json'] for r in mine)} | {sum((r.get('on_card') or 0) >= 0.999 for r in mine)} "
                         f"| {med([r['seconds'] for r in mine if r['stage'] == 'compose'])} | {med([r['seconds'] for r in mine if r['stage'] != 'compose'])} "
                         f"| {med([r['read_tps'] for r in mine if r['read_tps']])} | {med([r['write_tps'] for r in mine if r['write_tps']])} |")
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    top = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = top.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull")
    p.add_argument("models", nargs="+")
    f = sub.add_parser("fit")
    f.add_argument("models", nargs="+")
    f.add_argument("--ctx", default="8192,16384,32768")
    f.add_argument("--kv", default="f16,q8_0")
    r = sub.add_parser("run")
    r.add_argument("models", nargs="+")
    r.add_argument("--kv", default="q8_0")
    r.add_argument("--calls", type=int, default=24)
    sub.add_parser("report")
    x = top.parse_args()
    if x.cmd == "pull":
        pull(x.models)
    elif x.cmd == "fit":
        fit(x.models, [int(c) for c in x.ctx.split(",")], x.kv.split(","))
    elif x.cmd == "run":
        run(x.models, x.kv, x.calls)
    report()


if __name__ == "__main__":
    main()
