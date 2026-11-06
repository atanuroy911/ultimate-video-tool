"""Engine placement: use what is already installed as it is, or our own copy on its own port (vt/engines/placement.py)."""
import pytest

from vt import paths
from vt.engines import placement, store
from vt.engines.model import Endpoint
from vt.util import read_json


@pytest.fixture()
def machine(monkeypatch, tmp_path):
    """A pretend computer: `up` are the addresses that answer, `busy` the ports something else holds, `started` what we launched."""
    m = {"up": set(), "busy": set(), "started": []}
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(placement.hub, "reachable", lambda engine, url, timeout=1.5: url in m["up"])
    monkeypatch.setattr(placement, "_free", lambda port: port not in m["busy"] and f"http://127.0.0.1:{port}" not in m["up"])
    monkeypatch.setattr(placement, "own_installed", lambda engine: engine in m.get("installed", ()))
    from vt import llm

    monkeypatch.setattr(llm, "start_server", lambda url, wait=40, **kw: m["started"].append(url) or True)
    return m


def test_comfyui_already_running_on_two_cards_is_used_as_main_and_worker(machine):
    machine["up"] |= {"http://127.0.0.1:8188", "http://127.0.0.1:8189"}
    p = placement.place({"comfy": "auto"}, say=lambda *_: None)["comfy"]
    assert (p.source, p.url, p.workers) == ("existing", "http://127.0.0.1:8188", ["http://127.0.0.1:8189"])
    ep = store.load("comfy")
    assert ep.mode == "remote" and ep.all_urls() == ["http://127.0.0.1:8188", "http://127.0.0.1:8189"]
    assert read_json(paths.SETTINGS, {})["comfy_url"] == "http://127.0.0.1:8188"   # the older code reads this key


def test_an_existing_server_is_never_started_or_restarted(machine):
    machine["up"].add("http://127.0.0.1:11434")
    p = placement.place({"ollama": "auto"}, say=lambda *_: None)["ollama"]
    assert p.source == "existing" and machine["started"] == []


def test_our_own_copy_takes_its_own_port_and_keeps_it(machine):
    machine["up"].add("http://127.0.0.1:11434")                 # someone's Ollama is on the usual port: ours must not collide
    machine["busy"].add(11444)                                   # and something else holds our first choice
    p = placement.place({"ollama": "own"}, say=lambda *_: None)["ollama"]
    assert p.source == "own" and p.url == "http://127.0.0.1:11445" and machine["started"] == ["http://127.0.0.1:11445"]
    assert store.load("ollama").mode == "local"
    machine["busy"].clear()
    assert placement.decide("ollama", "own").url == "http://127.0.0.1:11445"   # remembered, not re-picked


def test_our_running_copy_is_not_mistaken_for_an_existing_install(machine):
    own = placement.own_url("comfy")
    machine["up"].add(own)
    machine["installed"] = ("comfy",)
    assert placement.decide("comfy", "auto").source == "own"


def test_nothing_installed_means_off_with_a_way_forward(machine):
    p = placement.decide("ollama", "auto")
    assert p.source == "off" and "vt engine setup" in p.note
    assert placement.decide("comfy", "existing").source == "off"


def test_an_address_given_is_used_and_a_saved_key_survives(machine):
    store.save("voicestudio", Endpoint(mode="remote", url="http://old:3900", key="secret"))
    p = placement.place({"voicestudio": "existing"}, {"voicestudio": "http://192.168.1.5:3900"}, say=lambda *_: None)["voicestudio"]
    assert p.url == "http://192.168.1.5:3900" and "does not answer" in p.note
    ep = store.load("voicestudio")
    assert ep.url == "http://192.168.1.5:3900" and ep.key == "secret"


def test_voicestudio_has_no_copy_of_its_own(machine):
    assert placement.decide("voicestudio", "own").source == "off"
    with pytest.raises(ValueError):
        placement.decide("ollama", "sometimes")


def test_the_engines_page_uses_the_same_placement(machine):
    from fastapi.testclient import TestClient

    from vt.server.app import app

    machine["up"] |= {"http://127.0.0.1:8188", "http://127.0.0.1:8189"}
    c = TestClient(app, client=("127.0.0.1", 50000))
    here = c.get("/api/engines/comfy/here").json()
    assert here["existing"] == ["http://127.0.0.1:8188", "http://127.0.0.1:8189"] and here["own_url"] == "http://127.0.0.1:8288"
    r = c.post("/api/engines/comfy/place", json={"choice": "existing"}).json()
    assert r["source"] == "existing" and r["workers"] == ["http://127.0.0.1:8189"]
    r = c.post("/api/engines/ollama/place", json={"choice": "existing"})
    assert r.status_code == 409 and "usual ports" in r.json()["detail"]
