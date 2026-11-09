"""Hardware detection, the setup state, the installer plans and the resumable download (docs/plans/PLAN-ENGINES-AND-SETUP.MD E4, E5). No network and no real install."""
import hashlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vt import paths
from vt.engines import hardware, installers, setup


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(installers.shutil, "disk_usage", lambda p: SimpleNamespace(free=int(2e12)))     # the space check is tested on its own
    return tmp_path


def test_a_computer_without_a_card_is_told_to_connect_a_server():
    hw = {"best_gpu": None, "ram_gb": 8}
    assert hardware.recommend(hw)["comfy"] == "remote" and hardware.recommend(hw)["ollama"] == "remote"
    assert "no NVIDIA" in hardware.summary([], 200)
    big = {"best_gpu": {"memory_gb": 16}, "ram_gb": 32}
    assert hardware.recommend(big)["comfy"] == "local" and "voicestudio" not in hardware.recommend(big)
    assert "Tesla" in hardware.summary([{"name": "Tesla V100", "memory_gb": 16.0}], 500) and "tight" in hardware.summary([{"name": "x", "memory_gb": 12.0}], 20)


def test_the_gpu_query_is_parsed(monkeypatch):
    monkeypatch.setattr(hardware.shutil, "which", lambda n: "nvidia-smi")
    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="0, Tesla V100-PCIE-16GB, 16384, 7.0\n1, NVIDIA GeForce RTX 3060, 12288, 8.6\n"))
    g = hardware.gpus()
    assert [x["name"] for x in g] == ["Tesla V100-PCIE-16GB", "NVIDIA GeForce RTX 3060"] and g[0]["bf16"] is False and g[1]["bf16"] is True and g[0]["memory_gb"] == 16.0


def test_the_pytorch_build_follows_the_card():
    assert installers.torch_index(7.0).endswith("cu126")        # the V100 lesson of 2026-10-26
    assert installers.torch_index(8.6).endswith("cu126") and installers.torch_index(12.0).endswith("cu128") and installers.torch_index(0).endswith("cpu")


def test_setup_state_is_resumable_and_validated(data):
    assert setup.state()["step"] == "welcome" and setup.state()["done"] is False
    destination=str(data/'model-store')  # storage paths belong to the OS executing the server
    s = setup.save(step="choose", choices={"comfy": "remote", "ollama": "local"}, models_dir=destination, bundles=["pictures", "bogus"])
    assert s["step"] == "choose" and s["choices"]["comfy"] == "remote" and s["models_dir"] == destination and s["bundles"] == ["pictures"]
    assert setup.state()["choices"]["ollama"] == "local"                       # survives a restart: it is in the settings file
    with pytest.raises(ValueError):
        setup.save(step="nowhere")
    with pytest.raises(ValueError):
        setup.save(choices={"comfy": "maybe"})
    with pytest.raises(ValueError):
        setup.save(choices={"toaster": "local"})


def test_the_comfy_plan_lists_models_sizes_and_what_is_already_there(data, monkeypatch):
    monkeypatch.setattr(installers.shutil, "which", lambda n: "git")
    inst = installers.ComfyInstaller(root=data / "comfy", models=str(data / "models"))
    p = inst.plan()
    names = [i.what for i in p.items]                       # the file each item downloads; the name says what it is for ("Picture model · ...")
    assert "z_image_turbo_bf16.safetensors" in names and "qwen_3_4b.safetensors" in names and "ae.safetensors" in names
    assert 20 < p.total_gb < 40 and not p.problems and str(data / "models") in p.notes[0]
    first = next(x for x in inst.manifest() if x["path"].endswith("ae.safetensors"))
    f = inst.models / first["path"]
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x" * first["size"]) if first["size"] < 10_000_000 else f.write_bytes(b"")
    assert inst.plan().total_gb <= p.total_gb
    monkeypatch.setattr(installers.shutil, "which", lambda n: None)
    assert any("Git" in x for x in inst.plan().problems)


def test_not_enough_space_is_said_before_anything_is_downloaded(data, monkeypatch):
    monkeypatch.setattr(installers.shutil, "which", lambda n: "git")
    monkeypatch.setattr(installers.shutil, "disk_usage", lambda p: SimpleNamespace(free=int(5e9)))
    p = installers.ComfyInstaller(root=data / "c", models=str(data / "m")).plan()
    assert any("free" in x for x in p.problems)


def test_the_install_runs_the_right_commands_in_order(data, monkeypatch):
    monkeypatch.setattr(installers.shutil, "which", lambda n: "git")
    inst = installers.ComfyInstaller(root=data / "comfy", models=str(data / "m"))
    ran = []
    monkeypatch.setattr(inst, "_run", lambda cmd: ran.append(cmd))
    monkeypatch.setattr(installers, "fetch", lambda url, dest, **k: ran.append(["fetch", dest.name]))
    inst.python = lambda: data / "comfy" / "py"                                  # type: ignore[method-assign]
    inst.install(compute=7.0)
    flat = [" ".join(c) for c in ran]
    assert flat[0].startswith("git clone --depth 1") and any("-m venv" in c for c in flat)
    assert any("--index-url https://download.pytorch.org/whl/cu126" in c for c in flat)
    assert flat.index(next(c for c in flat if "requirements.txt" in c)) > flat.index(next(c for c in flat if "index-url" in c))
    assert [c for c in flat if c.startswith("fetch")] and (data / "comfy" / "extra_model_paths.yaml").exists()
    yaml = (data / "comfy" / "extra_model_paths.yaml").read_text()
    assert str(data / "m").replace("\\", "/") in yaml and "diffusion_models" in yaml


class Resp:
    def __init__(self, code, body):
        self.status_code, self.body = code, body

    def iter_bytes(self, n):
        yield self.body

    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_a_download_resumes_and_is_checked(tmp_path):
    data = b"0123456789" * 100
    digest = hashlib.sha256(data).hexdigest()
    dest = tmp_path / "a" / "model.bin"
    part = dest.with_suffix(".bin.part")
    part.parent.mkdir(parents=True)
    part.write_bytes(data[:400])                                                  # an interrupted download
    seen = {}

    def opener(method, url, headers, **k):
        seen["range"] = headers.get("Range")
        return Resp(206, data[400:])

    installers.fetch("http://x/model.bin", dest, size=len(data), digest=digest, opener=opener)
    assert seen["range"] == "bytes=400-" and dest.read_bytes() == data and not part.exists()
    calls = []
    installers.fetch("http://x/model.bin", dest, size=len(data), digest=digest, opener=lambda *a, **k: calls.append(1))
    assert calls == [], "a complete file is not downloaded again"


def test_a_corrupt_download_is_deleted_and_named(tmp_path):
    dest = tmp_path / "m.bin"
    with pytest.raises(RuntimeError, match="checksum"):
        installers.fetch("http://x", dest, size=4, digest="0" * 64, opener=lambda *a, **k: Resp(200, b"abcd"))
    assert not dest.exists() and not dest.with_suffix(".bin.part").exists()


def test_the_setup_api(data):
    from vt.server.app import app

    with TestClient(app) as c:
        o = c.get("/api/setup").json()
        assert isinstance(o["bundles"],list) and "bundle_catalog" in o
        roundtrip=c.put('/api/setup',json={'choices':o['recommended'],'bundles':o['bundles']})
        assert roundtrip.status_code==200,roundtrip.text
        assert o["step"] == "welcome" and {"hardware", "recommended", "engines", "steps"} <= set(o) and {e["id"] for e in o["engines"]} == {"ollama", "comfy"}
        destination=str(data/'model-store')
        assert c.put("/api/setup", json={"step": "storage", "models_dir": destination}).json()["models_dir"] == destination
        assert c.put("/api/setup", json={"step": "x"}).status_code == 422
        assert c.get("/api/setup/plan?engines=toaster").status_code == 404
        plan = c.get("/api/setup/plan?engines=comfy&bundles=pictures").json()
        assert plan[0]["engine"] == "comfy" and plan[0]["items"]
        assert c.post("/api/setup/try/toaster").status_code == 404


def test_a_server_whose_engines_were_all_chosen_is_not_asked_to_set_up_again(data):
    # a server started with the launcher's engine flags (`--comfy existing --ollama existing`) has nothing left to ask
    from vt.engines import store
    from vt.engines.model import Endpoint

    assert setup.state()["done"] is False, "a brand new server still asks"
    store.save("ollama", Endpoint(mode="remote", url="http://127.0.0.1:11434"))
    assert setup.state()["done"] is False, "one engine still unchosen"
    store.save("comfy", Endpoint(mode="remote", url="http://127.0.0.1:8188"))
    assert setup.state()["done"] is True
    assert setup.state()["step"] == "welcome", "the wizard itself is still there to open from Settings"


def test_the_wizard_marks_every_model_against_the_card(data, monkeypatch):
    """A 6 GB laptop card: the language model that fits is recommended, the bigger one runs on the processor, clips are refused with a reason."""
    hw = {"ram_gb": 42.0, "gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4050 Laptop GPU", "memory_gb": 6, "compute": 8.9}]}
    m = setup.model_choices(hw, {})
    assert m["card"]["gb"] == 6 and m["language_default"] == "gemma3:4b"
    big = next(x for x in m["language"] if x["id"] == "gemma3:12b")
    assert big["speed"] == "slow" and "processor" in big["why"]
    assert not m["clips"]["fits"] and "12 GB" in m["clips"]["why"]
    blackwell = next(x for x in m["pictures"] if x["id"] == "zimage-nvfp4")
    assert not blackwell["fits"] and "RTX 50" in blackwell["why"]
    assert sum(x["recommended"] for x in m["pictures"]) == 1
    none = setup.model_choices({"ram_gb": 16.0, "gpus": []}, {})
    assert not any(x["fits"] for x in none["pictures"]) and not none["clips"]["fits"]


def test_a_chosen_model_is_saved_and_a_wrong_one_refused(data):
    setup.save(picture_model="klein-4b-fp8", language_model="gemma3:1b")
    s = setup.state()
    assert s["picture_model"] == "klein-4b-fp8" and s["language_model"] == "gemma3:1b"
    with pytest.raises(ValueError):
        setup.save(picture_model="not-a-model")
    with pytest.raises(ValueError):
        setup.save(language_model="llama-huge")


def test_the_folder_picker_lists_folders_never_files(data, tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir(); (tmp_path / "file.txt").write_text("x")
    f = setup.folders(str(tmp_path))
    assert [x["name"] for x in f["folders"]] == ["a", "b"] and f["writable"] and f["roots"]
    assert setup.folders(str(tmp_path / "not" / "yet"))["path"] == str(tmp_path)        # a folder not made yet shows the nearest one that is
    made = setup.new_folder(str(tmp_path), "Models")
    assert made["path"] == str(tmp_path / "Models") and (tmp_path / "Models").is_dir()
    with pytest.raises(ValueError):
        setup.new_folder(str(tmp_path), "bad/name")
    with pytest.raises(ValueError):
        setup.folders("relative/path")


def test_a_six_gb_card_is_offered_what_runs_well_first(monkeypatch):
    from vt.engines import setup

    hw = {"gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4050 Laptop GPU", "memory_gb": 6, "compute": 8.9}], "ram_gb": 42}
    m = setup.model_choices(hw, {})
    assert m["picture_default"] == "klein-4b-q4" and m["pictures"][0]["id"] == "klein-4b-q4" and m["pictures"][0]["speed"] == "fast"
    speeds = [p["speed"] or "no" for p in m["pictures"]]
    assert speeds == sorted(speeds, key=["fast", "slow", "no"].index)    # runs well, then slowly, then does not fit
    assert all("several times longer" in p["why"] for p in m["pictures"] if p["speed"] == "slow")
    monkeypatch.setattr(setup.hardware, "detect", lambda: hw)
    assert setup.chosen_picture_model({"picture_model": "klein-4b"}) == "klein-4b-q4"     # an old slow default gives way to the set that runs well
    assert setup.chosen_picture_model({"picture_model": "klein-4b-q3"}) == "klein-4b-q3"  # a choice that runs well is kept


def test_the_install_plan_adds_the_gguf_add_on_only_for_squeezed_sets(tmp_path):
    from vt.engines.installers import ComfyInstaller

    small = ComfyInstaller(root=tmp_path / "comfy", models=str(tmp_path / "m"), recipe="klein-4b-q4", gpu=0)
    names = [i.name for i in small.plan().items]
    assert "Add-on · ComfyUI-GGUF" in names and any("flux-2-klein-4b-Q4_K_M" in n for n in names) and any("Qwen3-4B-Q4_K_M" in n for n in names)
    big = ComfyInstaller(root=tmp_path / "comfy", models=str(tmp_path / "m"), recipe="klein-4b", gpu=0)
    assert not any(n.startswith("Add-on") for n in (i.name for i in big.plan().items))


def test_our_own_ollama_is_found_where_the_setup_installs_it(tmp_path, monkeypatch):
    """The setup installs Ollama into DATA/engines/ollama; after a restart Video Tool looked in DATA/ollama, found nothing and turned the Writing AI off (2026-11-09)."""
    from vt import llm, paths

    monkeypatch.setattr(paths, "DATA", tmp_path)
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    exe = "ollama.exe" if llm.WIN else "ollama"
    (tmp_path / "engines" / "ollama").mkdir(parents=True)
    (tmp_path / "engines" / "ollama" / exe).write_bytes(b"")
    assert llm.ollama_program_dir() == tmp_path / "engines" / "ollama"
    (tmp_path / "engines" / "ollama" / exe).unlink()
    (tmp_path / "ollama").mkdir()
    (tmp_path / "ollama" / exe).write_bytes(b"")
    assert llm.ollama_program_dir() == tmp_path / "ollama"            # an older copy is still found
