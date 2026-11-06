"""The owner's GPU server and its graphics cards (PLAN-PERFECT K6). Each step is explicit and can be run again.

    GPU_PASS=... python scripts/lab/server_cards.py report                      # read only: uptime, disk, ports, the cards, the owner's Ollama, what Video Tool says
    GPU_PASS=... python scripts/lab/server_cards.py allow "NVIDIA GeForce RTX 3060"     # which cards Video Tool may use (the Server page's switches, through the API)
    GPU_PASS=... python scripts/lab/server_cards.py own-ollama                  # Video Tool runs its own Ollama (port 11444, own folders, pinned to the allowed card)
    GPU_PASS=... python scripts/lab/server_cards.py pull gemma4:latest          # download a model into Video Tool's own Ollama (in the background on the server)
    GPU_PASS=... python scripts/lab/server_cards.py pull-status

It touches only Video Tool's own folder /home/roy/ultimate-video-tool-server (its run-server.sh, of which it keeps a copy) and Video Tool's own user service. It never touches the
owner's Ollama service, ComfyUI, /mnt/bigdata or any other folder. The password comes only from the GPU_PASS environment variable.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
import paramiko

HOST = "192.168.123.47"
ROOT = "/home/roy/ultimate-video-tool-server"
REPO = Path(__file__).resolve().parents[2]
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")


def api() -> httpx.Client:
    key = (REPO / "dist/recording-run/key.txt").read_text().strip()
    return httpx.Client(base_url=f"http://{HOST}:8790", headers={"Authorization": f"Bearer {key}"}, timeout=60)


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="roy", password=os.environ["GPU_PASS"], look_for_keys=False, allow_agent=False, timeout=20)
    return c


def sh(c, cmd: str, timeout: int = 120) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return (o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")).strip()


def running_jobs(a: httpx.Client) -> list[dict]:
    return [j for j in a.get("/api/jobs").json() if j["status"] in ("queued", "running")]


def report(c, a) -> None:
    print("uptime:      ", sh(c, "uptime -p; uptime -s").replace("\n", ", since "))
    print("disk:        ", sh(c, "df -h /home/roy | tail -1"))
    print("ports:       ", sh(c, "ss -ltn | grep -E ':(11434|11444|8188|8790) ' | awk '{print $4}' | tr '\\n' ' '"))
    print("owner Ollama:", sh(c, "systemctl show ollama -p ActiveState -p ActiveEnterTimestamp | tr '\\n' ' '"))
    print("our service: ", sh(c, "systemctl --user show ultimate-video-tool -p ActiveState -p ActiveEnterTimestamp | tr '\\n' ' '"))
    print("cards:\n" + "\n".join("   " + x for x in sh(c, "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader").splitlines()))
    print("programs on the cards:\n" + "\n".join("   " + x for x in (sh(c, "nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader") or "none").splitlines()))
    print("jobs running:", len(running_jobs(a)))
    d = a.get("/api/system/gpus").json()
    if "needs_choice" not in d:
        print("Video Tool: the server is running the older code (no card choice yet)")
        return
    print("Video Tool:   needs a choice:", d["needs_choice"], "| restart needed:", d["restart_needed"], "| saved list:", d["allowed_saved"])
    for card in d["cards"]:
        print(f"   GPU {card['index']} {card['name']}: {'MAY be used' if card['allowed'] else 'not used'}; " + (" ".join(f"{u['label']} {u['gb']} GB" for u in card["using"]) or "nothing on it"))
    print("   jobs:", {k: v["name"] for k, v in d["jobs"].items()})
    for e in d["engines"]:
        print(f"   {e['label']}: {e['code']} - {e['message']}")


def allow(c, a, cards: list[str]) -> None:
    r = a.put("/api/system/gpu", json={"allowed": [] if [x.lower() for x in cards] == ["none"] else cards})
    if r.status_code != 200:
        raise SystemExit(f"refused: {r.text[:300]}")
    d = r.json()
    print("allowed now:", [(x["index"], x["name"]) for x in d["cards"] if x["allowed"]], "| restarting:", d.get("restarting"))


def own_ollama(c, a) -> None:
    if running_jobs(a):
        raise SystemExit("a job is running; not restarting the server")
    before = sh(c, "systemctl show ollama -p ActiveEnterTimestamp")
    script = f"{ROOT}/run-server.sh"
    text = sh(c, f"cat {script}")
    new = text
    if "/usr/local/bin" not in new:
        new = new.replace('PATH="$ROOT/node/bin:/usr/bin:/bin"', 'PATH="$ROOT/node/bin:/usr/local/bin:/usr/bin:/bin"')
    new = new.replace("--ollama existing --ollama-url http://127.0.0.1:11434", "--ollama own")
    if new == text:
        print("run-server.sh already starts Video Tool's own Ollama")
    else:
        assert "--ollama own" in new and "/usr/local/bin" in new, "the start script is not what was expected; not changing it"
        sh(c, f"[ -e {script}.before-own-ollama ] || cp -p {script} {script}.before-own-ollama")
        s = c.open_sftp()
        with s.file(script, "w") as f:
            f.write(new if new.endswith("\n") else new + "\n")
        s.close()
        print("run-server.sh changed (a copy is kept as run-server.sh.before-own-ollama):")
        print(sh(c, f"grep -n -E 'PATH|ollama' {script}"))
    print(sh(c, "systemctl --user restart ultimate-video-tool.service && echo restarted"))
    for _ in range(60):
        time.sleep(2)
        try:
            if a.get("/api/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
    up = False
    for _ in range(40):
        if "version" in sh(c, "curl -s --max-time 3 http://127.0.0.1:11444/api/version"):
            up = True
            break
        time.sleep(2)
    print("own Ollama answers on 11444:", up)
    pid = sh(c, "ss -ltnp 2>/dev/null | grep ':11444 ' | sed -n 's/.*pid=\\([0-9]*\\).*/\\1/p' | head -1")
    if pid:
        env = sh(c, f"tr '\\0' '\\n' < /proc/{pid}/environ | grep -E '^(CUDA_VISIBLE_DEVICES|OLLAMA_HOST|OLLAMA_MODELS|HOME)='")
        print(f"its environment (pid {pid}):\n" + "\n".join("   " + x for x in env.splitlines()))
    after = sh(c, "systemctl show ollama -p ActiveEnterTimestamp")
    print("the owner's Ollama service:", "unchanged" if before == after else f"CHANGED: {before} -> {after}", "|", after)


def pull(c, a, model: str) -> None:
    if "version" not in sh(c, "curl -s --max-time 3 http://127.0.0.1:11444/api/version"):
        raise SystemExit("Video Tool's own Ollama does not answer on 11444 (run own-ollama first)")
    stem = f"{ROOT}/tmp/pull-{model.replace(':', '-').replace('/', '_')}"
    payload = json.dumps({"name": model})
    # a note of the process number, not a search for it by name (the command line of the shell that asks would match its own search)
    print(sh(c, f"mkdir -p {ROOT}/tmp; P=$(cat {stem}.pid 2>/dev/null); if [ -n \"$P\" ] && kill -0 $P 2>/dev/null; then echo 'already running'; "
                f"else nohup curl -sN http://127.0.0.1:11444/api/pull -d '{payload}' > {stem}.log 2>&1 & echo $! > {stem}.pid; echo started; fi"))
    print("follow it with: pull-status; log:", stem + ".log")


def pull_status(c, a) -> None:
    out = sh(c, f"ls -t {ROOT}/tmp/pull-*.log 2>/dev/null | head -1")
    if not out:
        print("no pull has been started")
        return
    stem = out[:-4]
    last = sh(c, f"tail -c 700 {out} | tr '\\r' '\\n' | tail -2")
    alive = sh(c, f"P=$(cat {stem}.pid 2>/dev/null); if [ -n \"$P\" ] && kill -0 $P 2>/dev/null; then echo yes; else echo no; fi")
    print(out)
    print(last)
    print("running:", alive, "| models in our Ollama:", sh(c, "curl -s --max-time 5 http://127.0.0.1:11444/api/tags | python3 -c \"import sys,json; print([m['name'] for m in json.load(sys.stdin)['models']])\""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report")
    p = sub.add_parser("allow")
    p.add_argument("cards", nargs="+", help="card names, numbers or uuids; or none")
    sub.add_parser("own-ollama")
    p = sub.add_parser("pull")
    p.add_argument("model")
    sub.add_parser("pull-status")
    x = ap.parse_args()
    client, web = ssh(), api()
    try:
        {"report": lambda: report(client, web), "allow": lambda: allow(client, web, x.cards), "own-ollama": lambda: own_ollama(client, web),
         "pull": lambda: pull(client, web, getattr(x, "model", "")), "pull-status": lambda: pull_status(client, web)}[x.cmd]()
    finally:
        client.close()
