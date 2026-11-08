"""The engines Video Tool runs itself start on the card of their job and restart when it changes (PLAN-PERFECT K3); an engine that was already running is never touched, but
when it sits on a card Video Tool may not use, that is said in plain words with the offer of Video Tool's own copy. Fake cards and real throw-away child programs stand in."""
import subprocess
import sys
import time

import pytest

from vt import gpuassign, paths, sysstats
from vt.engines import pids, placement, store, where
from vt.engines.model import Endpoint

V100 = {"index": 0, "name": "Tesla V100-PCIE-16GB", "uuid": "GPU-v100", "free_gb": 5.0, "total_gb": 16.0, "load": 96.0}
RTX = {"index": 1, "name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060", "free_gb": 9.0, "total_gb": 12.0, "load": 8.0}


class Box:
    def __init__(self):
        self.cards = [dict(V100), dict(RTX)]
        self.programs: dict[str, list] = {}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = Box()
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setattr(gpuassign, "_cards", lambda: [dict(c) for c in b.cards])
    monkeypatch.setattr(sysstats, "_gpus", lambda: [{"index": c["index"], "name": c["name"], "uuid": c["uuid"], "programs": list(b.programs.get(c["uuid"], []))} for c in b.cards])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "unset-by-the-test")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    pids._seen.clear()
    return b


@pytest.fixture()
def sleeper():
    """A harmless program that stays for a minute and has the words an engine's command line has; stopped at the end whatever happens."""
    started = []

    def start(*words):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", *words], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started.append(proc)
        for _ in range(100):                                       # the program has its own command line only once it has started (on Linux, between fork and exec it still has its parent's)
            if all(w in pids._cmdline(proc.pid) for w in words):
                break
            time.sleep(0.03)
        return proc

    yield start
    for p in started:
        if p.poll() is None:
            p.kill()
        p.wait(timeout=10)


# ----------------------------------------------------------------------------------------------------------------------------------- the jobs
def test_the_engines_have_jobs_of_their_own(box):
    assert gpuassign.JOBS == ("render", "speech", "ai", "pictures") and gpuassign.OWN_ENGINE_JOBS == {"ollama": "ai", "comfy": "pictures"}
    gpuassign.save({"allowed": "all", "ai": "GPU-3060", "pictures": "GPU-v100"})
    assert gpuassign.resolve("ai")[0]["uuid"] == "GPU-3060" and gpuassign.resolve("pictures")[0]["uuid"] == "GPU-v100"
    assert gpuassign.describe()["jobs"]["ai"]["name"] == "NVIDIA GeForce RTX 3060"
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.config()["pictures"] == "primary"                                      # the V100 left the list: its job goes back to following the primary card


def test_a_job_environment_shows_only_the_jobs_card(box):
    gpuassign.save({"allowed": "all", "ai": "GPU-3060"})
    assert gpuassign.job_env("ai") == {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": "GPU-3060"}
    gpuassign.save({"allowed": []})
    assert gpuassign.job_env("ai")["CUDA_VISIBLE_DEVICES"] == "-1"                          # no card allowed: the engine runs on the processor
    box.cards = []
    assert gpuassign.job_env("ai") == {}                                                    # no NVIDIA card here: nothing to pin


def test_which_jobs_a_save_can_move(box):
    assert gpuassign.affected_jobs({"allowed": ["x"]}) == set(gpuassign.JOBS) and gpuassign.affected_jobs({"primary": "auto"}) == set(gpuassign.JOBS)
    assert gpuassign.affected_jobs({"render": "primary"}) == {"render"} and gpuassign.affected_jobs({"ai": "GPU-3060", "speech": "primary"}) == {"ai", "speech"}


# ----------------------------------------------------------------------------------------------------------------------------------- starting our own copies on the job's card
def test_our_own_ollama_starts_with_its_own_folders_on_the_ai_card(box, monkeypatch, tmp_path):
    from vt import llm

    started = []
    up = {"yes": False}
    monkeypatch.setattr(llm, "reachable", lambda url=None, timeout=1.5: up["yes"])
    monkeypatch.setattr(placement.hub, "reachable", lambda name, url, timeout=1.5: up["yes"])
    monkeypatch.setattr(llm, "binary", lambda root=None: (started.append(("program_dir", root)) or "ollama"))
    monkeypatch.setattr(llm, "is_local", lambda url: True)
    monkeypatch.setattr(llm, "WIN", False)                                                  # the Linux and macOS way of starting it

    class Proc:
        pid = 4242

    def popen(cmd, **kw):
        started.append(("start", list(cmd), kw["env"]))
        up["yes"] = True
        return Proc()

    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    gpuassign.save({"allowed": ["GPU-3060"], "ai": "GPU-3060"})
    p = placement.decide("ollama", "own")
    placement.start(p, say=lambda *a: None)
    program = [x for x in started if x[0] == "program_dir"][0][1]
    start = [x for x in started if x[0] == "start"][0]
    assert program == paths.DATA / "engines" / "ollama"                                     # the program folder the installer uses, not whatever is first on the path
    assert start[2]["CUDA_VISIBLE_DEVICES"] == "GPU-3060" and start[2]["OLLAMA_MODELS"] == str(paths.DATA / "models" / "ollama")
    assert start[2]["HOME"] == str(paths.DATA / "engines" / "ollama-home")                  # its key and history are written there, not in the person's home folder
    assert start[2]["OLLAMA_HOST"] == p.url.replace("http://", "")                          # its own port, never the usual one
    assert pids.recorded("ollama")["pid"] == 4242 and pids.recorded("ollama")["port"] == int(p.url.rsplit(":", 1)[1])


def test_our_own_comfyui_starts_on_the_pictures_card_not_the_card_a_new_install_was_built_for(box, monkeypatch, tmp_path):
    from vt.engines import installers
    from vt.util import write_json

    seen = []

    class Proc:
        pid = 777

    monkeypatch.setattr(installers.subprocess, "Popen", lambda cmd, **kw: (seen.append(kw["env"]), Proc())[1])
    write_json(paths.SETTINGS, {"setup_gpu": 0})                                            # the wizard once built it for the V100
    gpuassign.save({"allowed": ["GPU-3060"]})
    installers.ComfyInstaller(root=tmp_path / "comfy", port=8288).start()
    assert seen[-1]["CUDA_VISIBLE_DEVICES"] == "GPU-3060"
    assert pids.recorded("comfy") == {**pids.recorded("comfy"), "pid": 777, "port": 8288}


# ----------------------------------------------------------------------------------------------------------------------------------- stopping only what we started
def test_a_process_is_ours_only_while_its_command_line_says_so(box, sleeper):
    proc = sleeper("ollama", "serve")
    pids.remember("ollama", proc.pid, 11444)
    assert pids.running("ollama", fresh=True) == proc.pid
    other = sleeper("some", "other", "program")                                             # a number now held by something else
    pids.remember("ollama", other.pid, 11444)
    assert pids.running("ollama", fresh=True) is None
    assert pids.stop("ollama") is False and other.poll() is None, "a program that is not the engine is never stopped"


def test_stop_ends_our_copy_and_only_that(box, sleeper):
    mine, theirs = sleeper("ollama", "serve"), sleeper("ollama", "serve")                  # theirs: the person's own Ollama, never recorded
    pids.remember("ollama", mine.pid, 11444)
    assert pids.stop("ollama") is True
    mine.wait(timeout=20)
    assert theirs.poll() is None
    assert pids.running("ollama", fresh=True) is None and pids.stop("ollama") is False


def test_comfyui_is_recognised_by_the_port_it_was_given(box, sleeper):
    proc = sleeper("main.py", "--listen", "127.0.0.1", "--port", "8288")
    pids.remember("comfy", proc.pid, 8288)
    assert pids.running("comfy", fresh=True) == proc.pid
    pids.remember("comfy", proc.pid, 8999)
    assert pids.running("comfy", fresh=True) is None


def test_a_change_of_card_restarts_our_running_copy_only(box, monkeypatch, sleeper):
    proc = sleeper("ollama", "serve")
    pids.remember("ollama", proc.pid, 11444)
    state = {"up": True, "started": []}
    monkeypatch.setattr(placement.hub, "reachable", lambda name, url, timeout=1.5: state["up"] and proc.poll() is None)
    monkeypatch.setattr(placement, "start", lambda p, say=print: state["started"].append(p.engine))
    assert placement.restart_own(["ollama", "comfy"], say=lambda *a: None) == ["ollama"]    # comfy was never started by us: left alone
    proc.wait(timeout=20)
    assert state["started"] == ["ollama"]
    assert placement.restart_own(["ollama"], say=lambda *a: None) == []                     # no longer running: nothing to restart


def test_the_server_restarts_an_engine_when_its_card_changes_and_not_otherwise(box, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from vt.server import system_routes

    calls = []
    monkeypatch.setattr(pids, "running", lambda engine, fresh=False: 99 if engine == "ollama" else None)
    monkeypatch.setattr(placement, "restart_own", lambda engines, say=print: calls.append(list(engines)) or list(engines))
    app = FastAPI()
    app.include_router(system_routes.router)
    c = TestClient(app)
    gpuassign.save({"allowed": "all", "primary": "GPU-v100"})
    r = c.put("/api/system/gpu", json={"primary": "GPU-3060"})                              # the primary card moves: the AI engine follows it
    assert r.status_code == 200 and r.json()["restarting"] == ["ollama"]
    for _ in range(50):
        if calls:
            break
        time.sleep(0.05)
    assert calls == [["ollama"]]
    r = c.put("/api/system/gpu", json={"render": "GPU-v100"})                               # a job that is not an engine's: nothing restarts
    assert r.json()["restarting"] == []
    r = c.put("/api/system/gpu", json={"primary": "GPU-3060"})                              # nothing changed
    assert r.json()["restarting"] == []


# ----------------------------------------------------------------------------------------------------------------------------------- saying where the engines run
def _existing(engine, url):
    store.save(engine, Endpoint(mode="remote", url=url))


def test_an_engine_that_was_already_running_on_a_card_that_is_not_allowed_is_reported_and_left_alone(box, monkeypatch):
    monkeypatch.setattr(placement, "own_installed", lambda engine: True)
    _existing("ollama", "http://127.0.0.1:11434")
    box.programs = {"GPU-v100": [{"label": "Ollama", "gb": 1.17, "pid": 55, "ours": False}, {"label": "python3", "gb": 9.7, "pid": 56, "ours": False}]}
    gpuassign.save({"allowed": ["GPU-3060"]})
    row = next(e for e in gpuassign.describe()["engines"] if e["id"] == "ollama")
    assert row["source"] == "existing" and row["code"] == "existing_blocked" and row["offer_own"] is True and row["own_installed"] is True
    assert "Tesla V100-PCIE-16GB (1.17 GB)" in row["message"] and "not allowed to use" in row["message"] and "own copy" in row["message"]
    assert store.load("ollama").url == "http://127.0.0.1:11434"                              # nothing was changed
    assert pids.running("ollama") is None


def test_an_existing_engine_on_an_allowed_card_is_only_described(box):
    _existing("comfy", "http://127.0.0.1:8188")
    box.programs = {"GPU-3060": [{"label": "ComfyUI", "gb": 6.0, "pid": 70, "ours": False}]}
    gpuassign.save({"allowed": "all"})
    row = next(e for e in where.report() if e["id"] == "comfy")
    assert row["code"] == "existing_on" and row["offer_own"] is False and "NVIDIA GeForce RTX 3060 (6.0 GB)" in row["message"]
    box.programs = {}
    assert next(e for e in where.report() if e["id"] == "comfy")["code"] == "existing_idle"


def test_our_own_copy_is_told_apart_from_the_one_that_was_already_there(box, sleeper):
    proc = sleeper("ollama", "serve")
    pids.remember("ollama", proc.pid, 11444)
    store.save("ollama", Endpoint(mode="local", url="http://127.0.0.1:11444"))
    box.programs = {"GPU-3060": [{"label": "Ollama", "gb": 3.0, "pid": proc.pid, "ours": False}], "GPU-v100": [{"label": "Ollama", "gb": 1.17, "pid": 55, "ours": False}]}
    gpuassign.save({"allowed": ["GPU-3060"]})
    row = next(e for e in where.report() if e["id"] == "ollama")
    assert row["source"] == "own" and row["code"] == "own_running" and row["offer_own"] is False
    assert "NVIDIA GeForce RTX 3060" in row["message"] and "V100" not in row["message"]      # the other Ollama on the V100 is not this row's business


def test_engines_on_other_computers_and_unused_ones(box):
    store.save("ollama", Endpoint(mode="remote", url="http://192.168.1.50:11434"))
    store.save("comfy", Endpoint(mode="off", url=""))
    rows = {e["id"]: e for e in where.report()}
    assert rows["ollama"]["code"] == "elsewhere" and "another computer" in rows["ollama"]["message"] and rows["ollama"]["offer_own"] is False
    assert rows["comfy"]["code"] == "off"


def test_using_our_own_copy_points_the_pipeline_at_it_and_starts_it_in_the_background(box, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from vt.server import system_routes

    started = []
    monkeypatch.setattr(placement, "start", lambda p, say=print: started.append((p.engine, p.url)))
    app = FastAPI()
    app.include_router(system_routes.router)
    c = TestClient(app)
    _existing("ollama", "http://127.0.0.1:11434")
    monkeypatch.setattr(placement, "own_installed", lambda engine: False)
    r = c.post("/api/system/engine-own", json={"engine": "ollama"})
    assert r.status_code == 409 and "not installed yet" in r.json()["detail"] and store.load("ollama").url == "http://127.0.0.1:11434"
    monkeypatch.setattr(placement, "own_installed", lambda engine: True)
    r = c.post("/api/system/engine-own", json={"engine": "ollama"})
    assert r.status_code == 200 and r.json()["starting"] is True and r.json()["source"] == "own"
    own = placement.own_url("ollama")
    assert store.load("ollama").mode == "local" and store.load("ollama").url == own
    for _ in range(50):
        if started:
            break
        time.sleep(0.05)
    assert started == [("ollama", own)]
    assert c.post("/api/system/engine-own", json={"engine": "nothing"}).status_code == 422


def test_vt_gpu_says_it_and_the_mcp_tool_offers_it(box, monkeypatch):
    from typer.testing import CliRunner

    from vt.cli import app
    from vt.mcp import server as mcp_server

    monkeypatch.setattr(placement, "own_installed", lambda engine: True)
    _existing("ollama", "http://127.0.0.1:11434")
    box.programs = {"GPU-v100": [{"label": "Ollama", "gb": 1.17, "pid": 55, "ours": False}]}
    gpuassign.save({"allowed": ["GPU-3060"]})
    shown = CliRunner().invoke(app, ["gpu"])
    assert shown.exit_code == 0 and "not allowed to use" in shown.output and "vt gpu own ollama" in shown.output
    done = []
    monkeypatch.setattr(where, "use_own", lambda engine, say=print: (done.append(engine), {"engine": engine, "source": "own", "url": "http://127.0.0.1:11444", "note": "x"})[1])
    assert CliRunner().invoke(app, ["gpu", "own", "ollama"]).exit_code == 0 and done == ["ollama"]
    tool = getattr(mcp_server.gpu_assignment, "fn", mcp_server.gpu_assignment)
    assert any(e["offer_own"] for e in tool()["engines"])
    tool(use_own_copy_of="comfy")
    assert done == ["ollama", "comfy"]


def test_the_command_line_and_the_mcp_tool_move_our_engines_too(box, monkeypatch):
    from typer.testing import CliRunner

    from vt.cli import app
    from vt.mcp import server as mcp_server

    calls = []
    monkeypatch.setattr(pids, "running", lambda engine, fresh=False: 99 if engine == "comfy" else None)
    monkeypatch.setattr(placement, "restart_own", lambda engines, say=print: calls.append(list(engines)) or list(engines))
    gpuassign.save({"allowed": "all", "pictures": "GPU-3060"})
    done = CliRunner().invoke(app, ["gpu", "set", "pictures", "0"])                         # the command line waits for the restart to finish before it ends
    assert done.exit_code == 0 and calls == [["comfy"]] and "restarted on its new card" in done.output
    tool = getattr(mcp_server.gpu_assignment, "fn", mcp_server.gpu_assignment)
    answer = tool(job="pictures", gpu="GPU-3060")
    assert answer["restarting"] == ["comfy"]
    for _ in range(50):
        if len(calls) == 2:
            break
        time.sleep(0.05)
    assert calls == [["comfy"], ["comfy"]]
    assert tool(job="render", gpu="GPU-v100")["restarting"] == []                           # a job no engine follows moves nothing


# ----------------------------------------------------------------------------------------------------------------------------------- setup no longer keeps a card of its own
def test_a_new_install_is_built_for_the_pictures_card_and_no_card_is_stored_for_it(box, tmp_path):
    from vt.engines import installers, setup
    from vt.util import read_json, write_json

    write_json(paths.SETTINGS, {"setup_gpu": 0})                                            # what an older version stored for the install: it is no longer read
    gpuassign.save({"allowed": "all", "pictures": "GPU-3060"})
    assert installers.ComfyInstaller(root=tmp_path / "c").gpu == 1 and setup.state()["gpu"] == 1
    assert installers.ComfyInstaller(root=tmp_path / "c", gpu=0).gpu == 0                   # a card named for one install still counts for that install
    setup.save(gpu=1)
    assert read_json(paths.SETTINGS, {})["setup_gpu"] == 0                                  # and nothing new is stored
    with pytest.raises(ValueError):
        setup.save(gpu=99)
    gpuassign.save({"allowed": []})
    assert setup.state()["gpu"] is None


def test_the_system_reading_tells_the_sidebar_that_a_choice_is_waiting(box, monkeypatch):
    full = {"percent": None, "memory_percent": None, "memory_used_gb": 0.0, "memory_total_gb": 12.0, "temperature_c": None, "power_w": None, "power_limit_w": None, "clock_mhz": None,
            "usable_by_video_tool": True, "programs": []}
    monkeypatch.setattr(sysstats, "_gpus", lambda: [{"index": c["index"], "name": c["name"], "uuid": c["uuid"], **full} for c in box.cards])
    assert sysstats.snapshot()["needs_gpu_choice"] is True
    gpuassign.save({"allowed": "all"})
    assert sysstats.snapshot()["needs_gpu_choice"] is False
