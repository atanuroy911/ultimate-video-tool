"""The test bench on the GPU server, for an agent working from this PC. All heavy work runs on the server, on the RTX 3060. Nothing runs on this PC's GPU.

    GPU_PASS=... python scripts/lab/vt_lab.py make <director> <style> <name> [--aspect 9:16] [--lang en] [--engine kokoro] [--voice af_heart] [--script-file f] [--template classic]
    python scripts/lab/vt_lab.py helper start|status|stop                # Claude and Codex on this PC as the server's directors, through the real helper program (client/desktop/helper.js), with no app. `start` prints the id for `make`
    python scripts/lab/vt_lab.py export <project> [--aspect 9:16]        # renders; waits
    GPU_PASS=... python scripts/lab/vt_lab.py sheet <project> <name>     # contact sheet of the newest export: dist/lab/<name>.png
    GPU_PASS=... python scripts/lab/vt_lab.py frames <project> <name> <t1,t2,...>   # the deployed code's frames, side by side: dist/lab/<name>.png
    GPU_PASS=... python scripts/lab/vt_lab.py facts <project> <t1,t2,...>           # what covers what, measured
    python scripts/lab/vt_lab.py report <project>                        # who directed, every AI conversation, the frame review
    GPU_PASS=... python scripts/lab/vt_lab.py judge <project> [--file name.mp4]    # read-only D1 checks on an existing export
    GPU_PASS=... python scripts/lab/vt_lab.py tests [pytest args]        # the whole repository on the server in /home/roy/vt-tests/repo; results also in /home/roy/vt-tests/last.txt
    GPU_PASS=... python scripts/lab/vt_lab.py scratch start [--fresh]|stop   # a second server on port 8792 for browser tests (own code copy and data); the key goes to dist/lab/scratch-key.txt

<director> is local (gemma on the server; see docs/plans/PLAN-PERFECT.MD step K6 first, because it can land on the V100), claude-server, best, or Claude or Codex on this PC: run `helper start` and use the id it prints (claude@<device>). It is the same path the app uses, so `make` then does every AI step through it.
<style> is one of reel, story, explainer, stick, cartoon, emoji, infographic, mixed, auto: the New page's choice.
The password comes only from the GPU_PASS environment variable. Never write it to a file. The server's API key is read from dist/recording-run/key.txt.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "dist" / "lab"
HOST = "192.168.123.47"
API = f"http://{HOST}:8790"
ROOT = "/home/roy/ultimate-video-tool-server"
TESTS = "/home/roy/vt-tests"
STORY = ("Maya saved every coin for a whole year. She wanted one thing, a red bicycle. Every morning she walked past the shop and looked through the window. "
         "Her mother asked why she never bought sweets anymore. Maya only smiled. On her birthday she counted two hundred and fifty dollars. "
         "She ran to the shop before it opened at ten o'clock. The owner laughed and handed her the keys. That evening she rode home with her mother running beside her.")
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")


def api() -> httpx.Client:
    key = (REPO / "dist/recording-run/key.txt").read_text().strip()
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {key}"}, timeout=120)


def ssh():
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="roy", password=os.environ["GPU_PASS"], look_for_keys=False, allow_agent=False, timeout=20)
    return c


def sh(c, cmd: str, timeout: int = 280) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")


def remote_python(c, code: str, timeout: int = 280) -> str:
    """Runs on the server with the deployed code, on the RTX 3060."""
    with c.open_sftp().file("/tmp/vt_lab_run.py", "w") as f:
        f.write(code)
    return sh(c, f"cd {ROOT}/app && CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID VT_DATA={ROOT}/data {ROOT}/venv/bin/python /tmp/vt_lab_run.py", timeout)


def wait_job(a: httpx.Client, job: str, limit: float = 1500) -> dict:
    last, t0 = "", time.time()
    while time.time() - t0 < limit:
        j = a.get(f"/api/jobs/{job}").json()
        now = f'{j.get("status")} | {j.get("stage")} | {j.get("msg")}'
        if now != last:
            print(time.strftime("%H:%M:%S"), now, flush=True)
            last = now
        if j.get("status") in ("done", "error", "failed", "cancelled"):
            return j
        time.sleep(3)
    raise SystemExit(f"job {job} still not finished after {limit} s")


def make(x) -> None:
    script = Path(x.script_file).read_text(encoding="utf-8") if x.script_file else STORY
    style = x.style
    kind = "explainer" if style in ("auto", "reel", "story") else style                # the same mapping as client/studio/src/pages/New.tsx
    options = {"director": x.director, "music": "auto"}
    if style in ("reel", "story"):
        options["look"] = style
    if style == "cartoon":
        options["cartoon_template"] = x.template
    a = api()
    r = a.post("/api/projects/from-script", json={"title": x.name, "script": script, "language": x.lang, "engine": x.engine, "voice": x.voice, "aspect": x.aspect, "theme": "auto", "kind": kind, "options": options})
    r.raise_for_status()
    d = r.json()
    print(d["project"]["id"], flush=True)
    j = wait_job(a, d["job"]["id"])
    print("job:", j.get("status"), j.get("error") or "")
    report_for(a, d["project"]["id"])


HELPER = OUT / "helper"                           # the lab helper's own folder (device id, saved servers, run file, log). The app's helper keeps another, so the two never meet.


def helper_name() -> str:
    return f"{socket.gethostname()} (lab)"           # the Server page and the director list show it as "Claude on <this PC> (lab)"


def helper_ask(method: str, route: str, body: dict | None = None) -> dict | None:
    """The lab helper's own local API (its port and key are in its run file). None when nothing answers."""
    try:
        run = json.loads((HELPER / "helper-run.json").read_text(encoding="utf-8"))
        r = httpx.request(method, f"http://127.0.0.1:{run['port']}{route}", headers={"Authorization": f"Bearer {run['key']}"}, json=body, timeout=5)
        return r.json()
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        return None


def helper_device() -> str:
    try:
        return json.loads((HELPER / "device.json").read_text(encoding="utf-8"))["id"]
    except (OSError, ValueError, KeyError):
        return ""


def helper_listed() -> list[dict]:
    """What the server lists for this helper's device (the director ids a video can be made with)."""
    device = helper_device()
    return [d for d in api().get("/api/directors").json()["directors"] if device and d.get("device") == device]


def helper_show() -> None:
    info = helper_ask("GET", "/status")
    if info is None:
        print("the lab helper is not running (start it: vt_lab.py helper start)")
        return
    print(f"the lab helper is running: pid {info['pid']}, version {info['version']}, {info.get('rss_mb')} MB, device {helper_device()}, named \"{helper_name()}\"")
    for s in info["servers"]:
        print(f"  server {s['server']}: {s['state']}" + (f" ({s['last_error']})" if s.get("last_error") else ""))
    for kind, a in info["assistants"].items():
        print(f"  {kind} on this PC: " + (f"{a['version']}, " + ("signed in" if a["logged_in"] else "NOT signed in") if a["found"] else "not installed"))
    listed = helper_listed()
    for d in listed:
        print(f"  the server lists it as {d['id']}: {d['label']} | {'ready' if d['available'] else 'not ready'} | {d.get('note', '')}")
    if not listed:
        print("  the server does not list it (yet)")


def helper(x) -> None:
    """Claude and Codex on this PC as the server's directors, with no app: the real helper program under plain Node, in its own folder and with a name of its own."""
    HELPER.mkdir(parents=True, exist_ok=True)
    if x.action == "status":
        helper_show()
        return
    if x.action == "stop":
        if helper_ask("POST", "/stop", {}) is None:
            print("the lab helper was not running")
            return
        for _ in range(40):
            if not (HELPER / "helper-run.json").exists():
                break
            time.sleep(0.25)
        print("the lab helper stopped (the server now lists its computer as not connected)")
        return
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node is not installed on this PC, so the helper cannot run.")
    if helper_ask("GET", "/status") is None:
        env = {**os.environ, "VT_HELPER_HOME": str(HELPER), "VT_HELPER_NAME": helper_name()}
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        subprocess.Popen([node, str(REPO / "client/desktop/helper.js")], env=env, cwd=str(HELPER), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach)
        for _ in range(60):
            if helper_ask("GET", "/status") is not None:
                break
            time.sleep(0.25)
        else:
            raise SystemExit(f"the helper did not start; see {HELPER / 'helper.log'}")
    helper_ask("POST", "/servers", {"server": API})                  # its own network: the address is enough, no key (PLAN-PERFECT M5b)
    for _ in range(40):
        if any(d["available"] for d in helper_listed()):
            break
        time.sleep(1)
    helper_show()
    ready = [d["id"] for d in helper_listed() if d["available"]]
    if ready:
        print("use it: " + " | ".join(f"vt_lab.py make {i} <style> <name>" for i in ready))
    else:
        print("the server does not list a ready director for it; read the lines above (and " + str(HELPER / "helper.log") + ")")


def export(x) -> None:
    a = api()
    r = a.post(f"/api/projects/{x.project}/export", json={"aspects": [x.aspect]})
    r.raise_for_status()
    j = wait_job(a, r.json().get("job", r.json())["id"])
    print("export:", j.get("status"), j.get("error") or "")


def sheet(x) -> None:
    c = ssh()
    Q = f"{ROOT}/data/projects/{x.project}"
    print(sh(c, f"cd {Q} && M=$(ls -t exports/*.mp4 | head -1); echo $M; ffmpeg -y -v error -i \"$M\" -vf 'fps=1/{x.every},scale=270:-1,tile=6x3' -frames:v 1 /tmp/{x.name}.png"))
    OUT.mkdir(parents=True, exist_ok=True)
    c.open_sftp().get(f"/tmp/{x.name}.png", str(OUT / f"{x.name}.png"))
    print("saved", OUT / f"{x.name}.png")


def frames(x) -> None:
    c = ssh()
    out = remote_python(c, f"""
from vt.project import Project
from vt.pipeline import compose_all
from vt.render.hyperframes import snapshot
from vt.compose import FORMATS
p = Project({x.project!r})
compose_all(p)
for f in snapshot(p.comp_dir / FORMATS[p.meta().aspect]["tag"], p.dir / "snapshots", [{x.times}]):
    print(f)
""")
    files = [ln for ln in out.splitlines() if ln.endswith(".png")]
    if not files:
        raise SystemExit(out[-1500:])
    inputs = " ".join(f"-i '{f}'" for f in files)
    scale = "".join(f"[{i}]scale=360:-1[v{i}];" for i in range(len(files))) + "".join(f"[v{i}]" for i in range(len(files))) + f"hstack=inputs={len(files)}"
    cmd = f"ffmpeg -y -v error {inputs} -filter_complex \"{scale}\" /tmp/{x.name}.png" if len(files) > 1 else f"ffmpeg -y -v error {inputs} -vf scale=540:-1 /tmp/{x.name}.png"
    print(sh(c, cmd, 100))
    OUT.mkdir(parents=True, exist_ok=True)
    c.open_sftp().get(f"/tmp/{x.name}.png", str(OUT / f"{x.name}.png"))
    print("saved", OUT / f"{x.name}.png")


def facts(x) -> None:
    print(remote_python(ssh(), f"""
import json
from vt.project import Project
from vt.pipeline import compose_all
from vt.render.hyperframes import frame_facts
from vt.compose import FORMATS
p = Project({x.project!r})
compose_all(p)
print(json.dumps(frame_facts(p.comp_dir / FORMATS[p.meta().aspect]["tag"], [{x.times}]), indent=1, ensure_ascii=False))
""")[-6000:])


def report_for(a: httpx.Client, pid: str) -> None:
    p = a.get(f"/api/projects/{pid}").json()
    rows = a.get(f"/api/projects/{pid}/ai-talk").json()["rows"]
    print("status:", p.get("status"), "| notice:", (p.get("ai_notice") or {}).get("message"))
    print("director:", json.dumps(p.get("director_used") or p.get("director"), ensure_ascii=False)[:200])
    print("AI conversations:", len(rows), sorted({f'{r["who"]}/{r["model"]}' for r in rows}))
    for r in rows:
        if r["error"]:
            print("  error:", r["stage"], r["who"], r["error"][:200])


def report(x) -> None:
    report_for(api(), x.project)


def judge(x) -> None:
    args = [x.project, "--data", str(x.data.resolve()) if x.data else f"{ROOT}/data"]
    if x.file:
        args += ["--file", x.file]
    if x.data:
        # paths.ensure_data() is normally called on import. Keep that away
        # from the data being judged and pass the read-only store separately.
        env = {**os.environ, "VT_DATA": str(REPO / "server"), "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run([sys.executable, "-m", "vt.lab_judge", *args], cwd=REPO / "server", env=env)
        raise SystemExit(result.returncode)

    cmd = (f"cd {shlex.quote(ROOT + '/app')} && "
           f"VT_DATA={shlex.quote(ROOT + '/app')} PYTHONIOENCODING=utf-8 "
           + shlex.join([f"{ROOT}/venv/bin/python", "-m", "vt.lab_judge", *args]))
    with ssh() as connection:
        # Merge the streams so a large browser diagnostic cannot block its
        # pipe while stdout waits. Preserve the remote judge's exit code.
        channel = connection.get_transport().open_session(timeout=20)
        channel.set_combine_stderr(True)
        channel.settimeout(900)
        channel.exec_command(cmd)
        for line in channel.makefile("rb"):
            print(line.decode("utf-8", "replace"), end="", flush=True)
        raise SystemExit(channel.recv_exit_status())


def pack_repo() -> bytes:
    """The working tree as a .tgz: git's own list (untracked files count, ignored ones do not), plus the recordings git keeps out."""
    names = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=REPO, capture_output=True).stdout.decode("utf-8", "replace").split("\0")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for n in names:
            f = REPO / n
            if n and f.is_file() and not f.is_symlink() and f.stat().st_size < 60_000_000 and "node_modules" not in f.parts and not n.startswith("dist/"):
                t.add(f, arcname=n)
        for f in [*(REPO / "samples/audio").glob("*.*"), REPO / "english sample.mp3"]:       # kept out of git, and the recording tests skip themselves without them
            if f.is_file() and f.relative_to(REPO).as_posix() not in names:
                t.add(f, arcname=f.relative_to(REPO).as_posix())
    return buf.getvalue()


def link_repo(dest: str) -> str:
    """Shell: what a copy of the repo takes from the deployed app, so it needs no downloads of its own."""
    return f"""cd {dest}/server/renderer; ln -sfn {ROOT}/app/renderer/node_modules node_modules; cd ../..
for x in design assets; do rm -rf server/$x; ln -s {ROOT}/app/$x server/$x; done
cp -n {ROOT}/app/renderer/runtime/* server/renderer/runtime/ 2>/dev/null || true"""


def tests(x) -> None:
    extra = " ".join(x.args) or "../tests"
    c = ssh()
    sh(c, f"mkdir -p {TESTS}")
    with c.open_sftp().file(f"{TESTS}/code.tgz", "wb") as f:
        f.write(pack_repo())
    cmd = f"""set -e; cd {TESTS}; rm -rf repo data; mkdir -p repo data; tar -xzf code.tgz -C repo 2>/dev/null; rm code.tgz
[ -d pydeps/pytest ] || {{ curl -sS -m 60 -L -o /tmp/vt-pip.pyz https://bootstrap.pypa.io/pip/pip.pyz; {ROOT}/venv/bin/python /tmp/vt-pip.pyz install -q --target pydeps pytest jsonschema; }}
{link_repo(TESTS + '/repo')}
export PYTHONPATH={TESTS}/pydeps:{TESTS}/repo/server CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID VT_DATA={TESTS}/data HYPERFRAMES_NO_TELEMETRY=1
cd server; timeout 1700 {ROOT}/venv/bin/python -m pytest -q -p no:cacheprovider -W ignore -c /dev/null --rootdir={TESTS}/repo --tb=line {extra} > {TESTS}/last.txt 2>&1 || true; tail -120 {TESTS}/last.txt"""
    print(sh(c, cmd, 1800)[-14000:])


SCRATCH = f"{TESTS}/scratch"                       # the scratch server's own data folder (VT_DATA)
SCRATCH_REPO = f"{TESTS}/scratch-repo"
SCRATCH_PORT = 8792


def scratch(x) -> None:
    """A second Video Tool server for browser tests: its own code copy, data folder and port, on the RTX 3060. It is told about ComfyUI on 8188 (used as it is, never changed) and
    nothing else: Ollama is off, so nothing here can start or change the owner's engines."""
    c = ssh()
    pidfile = f"{TESTS}/scratch.pid"
    ours = f"P=$(cat {pidfile} 2>/dev/null); [ -n \"$P\" ] && grep -qa Scratch /proc/$P/cmdline 2>/dev/null && grep -qa {SCRATCH_PORT} /proc/$P/cmdline"
    stop = f"{ours} && {{ kill $P; sleep 3; kill -0 $P 2>/dev/null && kill -9 $P; rm -f {pidfile}; echo 'scratch server stopped'; }} || echo 'the scratch server was not running'"
    if x.action == "stop":
        print(sh(c, stop).strip())
        return
    print(sh(c, stop).strip())                                              # start always means the code as it is now
    if sh(c, f"ss -ltn | grep -c ':{SCRATCH_PORT} ' || true").strip() != "0":
        raise SystemExit(f"port {SCRATCH_PORT} is used by something that is not the scratch server; not starting.")
    sh(c, f"mkdir -p {TESTS}/tmp")
    with c.open_sftp().file(f"{TESTS}/scratch-code.tgz", "wb") as f:
        f.write(pack_repo())
    fresh = f"rm -rf {SCRATCH}; " if x.fresh else ""
    env = (f"VT_DATA={SCRATCH} TMPDIR={TESTS}/tmp PATH={ROOT}/node/bin:/usr/bin:/bin HYPERFRAMES_NO_TELEMETRY=1 PYTHONIOENCODING=utf-8 "
           f"CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONPATH={SCRATCH_REPO}/server")
    py = f"{ROOT}/venv/bin/python"
    print(sh(c, f"""set -e; cd {TESTS}; rm -rf scratch-repo; mkdir -p scratch-repo; {fresh}mkdir -p {SCRATCH}; tar -xzf scratch-code.tgz -C scratch-repo 2>/dev/null; rm scratch-code.tgz
{link_repo(SCRATCH_REPO)}
cd {SCRATCH_REPO}; env {env} {py} samples/build_reference.py reference
cd {SCRATCH_REPO}/server; setsid nohup bash -c 'echo $$ > {pidfile}; exec env {env} {py} -m vt.cli server --host 0.0.0.0 --port {SCRATCH_PORT} --name Scratch --comfy existing --comfy-url http://127.0.0.1:8188 --ollama off' > {TESTS}/scratch.log 2>&1 < /dev/null &
sleep 1; echo started""").strip())
    for _ in range(45):
        time.sleep(2)
        if sh(c, f"curl -s -o /dev/null -w '%{{http_code}}' -m 3 http://127.0.0.1:{SCRATCH_PORT}/ || true").strip() not in ("", "000"):
            break
    else:
        raise SystemExit("the scratch server did not answer in 90 s; see " + TESTS + "/scratch.log")
    key = json.loads(sh(c, f"cat {SCRATCH}/engine-hub.json"))["key"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scratch-key.txt").write_text(key, encoding="utf-8")
    print(f"scratch server up at http://{HOST}:{SCRATCH_PORT}; its key is in dist/lab/scratch-key.txt (never print it).")
    print(f"Studio against it: cd client/studio && VT_SERVER_URL=http://{HOST}:{SCRATCH_PORT} VT_SERVER_KEY=$(cat ../../dist/lab/scratch-key.txt) npx vite --port 5175 --strictPort --host 127.0.0.1")
    print("Browser suites:    VT_URL=http://127.0.0.1:5175 VT_PROJECT=reference node e2e/dashboard.mjs")


if __name__ == "__main__":
    top = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = top.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("make")
    p.add_argument("director")
    p.add_argument("style")
    p.add_argument("name")
    p.add_argument("--aspect", default="9:16")
    p.add_argument("--lang", default="en")
    p.add_argument("--engine", default="kokoro")
    p.add_argument("--voice", default="af_heart")
    p.add_argument("--script-file")
    p.add_argument("--template", default="classic")
    p.set_defaults(fn=make)
    p = sub.add_parser("helper")
    p.add_argument("action", choices=["start", "status", "stop"])
    p.set_defaults(fn=helper)
    p = sub.add_parser("export")
    p.add_argument("project")
    p.add_argument("--aspect", default="9:16")
    p.set_defaults(fn=export)
    p = sub.add_parser("sheet")
    p.add_argument("project")
    p.add_argument("name")
    p.add_argument("--every", default="2")
    p.set_defaults(fn=sheet)
    p = sub.add_parser("frames")
    p.add_argument("project")
    p.add_argument("name")
    p.add_argument("times")
    p.set_defaults(fn=frames)
    p = sub.add_parser("facts")
    p.add_argument("project")
    p.add_argument("times")
    p.set_defaults(fn=facts)
    p = sub.add_parser("report")
    p.add_argument("project")
    p.set_defaults(fn=report)
    p = sub.add_parser("judge", help="Check an existing video and its composition")
    p.add_argument("project")
    p.add_argument("--file", help="Export filename. Defaults to the newest finished MP4")
    p.add_argument("--data", type=Path, help="Read a local data folder instead of connecting to the lab server")
    p.set_defaults(fn=judge)
    p = sub.add_parser("tests")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(fn=tests)
    p = sub.add_parser("scratch")
    p.add_argument("action", choices=["start", "stop"])
    p.add_argument("--fresh", action="store_true", help="start: empty the scratch data folder first")
    p.set_defaults(fn=scratch)
    a = top.parse_args()
    a.fn(a)
