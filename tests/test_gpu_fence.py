"""The allowed cards are a fence (PLAN-PERFECT K2): the server fences itself at start, and every place that draws, encodes or computes on a card follows the list.
Fake cards and fake programs stand in for nvidia-smi, ffmpeg and the renderer, so this runs on any machine and never touches a real card."""
import os
from types import SimpleNamespace

import pytest

from vt import gpu, gpuassign, paths, sysstats

V100 = {"index": 0, "name": "Tesla V100-PCIE-16GB", "uuid": "GPU-v100", "free_gb": 5.0, "total_gb": 16.0, "load": 96.0}
RTX = {"index": 1, "name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060", "free_gb": 9.0, "total_gb": 12.0, "load": 8.0}
TRAINING = {"label": "python3", "gb": 9.7, "ours": False}


class Box:
    def __init__(self):
        self.cards = [dict(V100), dict(RTX)]
        self.programs: dict[str, list] = {}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = Box()
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(gpuassign, "_cards", lambda: [dict(c) for c in b.cards])
    monkeypatch.setattr(gpuassign, "_PIN", None)
    monkeypatch.setattr(gpuassign, "_APPLIED", None)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "unset-by-the-test")                  # so that monkeypatch puts back whatever apply() writes
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    monkeypatch.setattr(sysstats, "_gpus", lambda: [{"index": c["index"], "name": c["name"], "uuid": c["uuid"], "programs": list(b.programs.get(c["uuid"], []))} for c in b.cards])
    return b


# ----------------------------------------------------------------------------------------------------------------------------------- the fence at start
def test_apply_fences_the_process_to_the_allowed_cards_in_the_drivers_order(box):
    gpuassign.save({"allowed": ["GPU-3060", "GPU-v100"]})
    assert gpuassign.apply() == ["GPU-v100", "GPU-3060"]
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-v100,GPU-3060"
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.apply() == ["GPU-3060"] and os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060"
    assert gpuassign.cuda_index("speech") == 0                                          # fenced to the 3060: it is the only one this process sees


def test_applying_twice_changes_nothing_because_the_fence_is_the_launchers_not_ours(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    gpuassign.apply()
    gpuassign.apply()
    assert [c["uuid"] for c in gpuassign.allowed()] == ["GPU-3060"] and os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060"


def test_no_card_allowed_hides_every_card(box):
    gpuassign.save({"allowed": []})
    assert gpuassign.apply() == [] and os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
    assert gpuassign.blocked()


def test_before_the_person_answers_the_server_still_fences_itself_to_the_one_card_it_uses(box):
    box.programs = {"GPU-v100": [TRAINING]}
    assert gpuassign.apply() == ["GPU-3060"] and os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060"


def test_no_nvidia_card_and_no_answer_leaves_the_environment_alone(box):
    box.cards = []
    assert gpuassign.apply() == [] and "CUDA_VISIBLE_DEVICES" not in os.environ
    assert not gpuassign.blocked()                                                      # nothing to forbid on a computer without a card


def test_when_nvidia_smi_does_not_answer_the_saved_answer_is_used_as_it_is(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    box.cards = []                                                                      # the program that lists the cards fails this once
    assert gpuassign.apply() == ["GPU-3060"] and os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060"


def test_a_change_after_start_asks_for_a_restart_and_changing_back_cancels_it(box):
    gpuassign.save({"allowed": "all"})
    gpuassign.apply()
    assert not gpuassign.restart_needed() and gpuassign.describe()["restart_needed"] is False
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.restart_needed() and gpuassign.describe()["restart_needed"] is True
    gpuassign.save({"allowed": "all"})
    assert not gpuassign.restart_needed()


def test_a_server_that_was_never_fenced_and_one_nobody_has_answered_do_not_ask_for_a_restart(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert not gpuassign.restart_needed()                                               # never applied (a command line tool, a test)


def test_the_default_flipping_is_not_a_restart(box):
    box.programs = {"GPU-v100": [TRAINING]}
    gpuassign.apply()
    box.programs = {"GPU-3060": [TRAINING]}                                             # the training moved: the default is now the other card, but nobody answered
    assert not gpuassign.restart_needed()


def test_the_server_start_fences_and_says_so(box, monkeypatch, capsys):
    from vt import cli

    monkeypatch.setattr(cli, "_fenced", False)
    gpuassign.save({"allowed": ["GPU-3060"]})
    cli._fence()
    out = capsys.readouterr().out
    assert "Graphics cards Video Tool may use: 1 NVIDIA GeForce RTX 3060" in out and os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060"
    monkeypatch.setattr(cli, "_fenced", False)
    gpuassign.save({"allowed": []})
    cli._fence()
    assert "none (the processor does the work)" in capsys.readouterr().out


def test_unanswered_with_two_cards_the_start_says_to_choose(box, monkeypatch, capsys):
    from vt import cli

    monkeypatch.setattr(cli, "_fenced", False)
    cli._fence()
    out = capsys.readouterr().out
    assert "Nobody has chosen yet" in out and "vt gpu allow" in out


# ----------------------------------------------------------------------------------------------------------------------------------- the browser that draws the frames
def _smi_rows(cards):
    return "\n".join(f"{c['index']}, {c['name']}, {c['uuid']}, {int(c['free_gb'] * 1024)}" for c in cards) + "\n"


def test_the_renderer_probes_and_uses_only_allowed_cards(box, monkeypatch):
    from vt.render import browser_gpu

    probed = []

    def fake_run(cmd, env=None, **kw):
        probed.append(env["CUDA_VISIBLE_DEVICES"])
        return SimpleNamespace(returncode=1, stderr=b"no")                              # every probe fails, so every card that may be tried is tried

    monkeypatch.setattr(browser_gpu.subprocess, "check_output", lambda *a, **k: _smi_rows(box.cards))
    monkeypatch.setattr(browser_gpu.subprocess, "run", fake_run)
    monkeypatch.setattr(browser_gpu, "find_tool", lambda name: name)
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert browser_gpu.nvidia_render_device() is None
    assert probed == ["GPU-3060"]                                                       # the V100 was never even tried as a fallback
    probed.clear()
    gpuassign.save({"allowed": "all"})
    browser_gpu.nvidia_render_device()
    assert sorted(probed) == ["GPU-3060", "GPU-v100"]
    probed.clear()
    gpuassign.save({"allowed": []})
    assert browser_gpu.nvidia_render_device() is None and probed == []


def test_the_renderer_picks_the_card_the_person_chose_first_among_the_allowed(box, monkeypatch):
    from vt.render import browser_gpu

    monkeypatch.setattr(browser_gpu.subprocess, "check_output", lambda *a, **k: _smi_rows(box.cards))
    monkeypatch.setattr(browser_gpu.subprocess, "run", lambda cmd, env=None, **kw: SimpleNamespace(returncode=0, stderr=b""))
    monkeypatch.setattr(browser_gpu, "find_tool", lambda name: name)
    gpuassign.save({"allowed": "all", "render": "GPU-v100"})
    assert browser_gpu.nvidia_render_device()["uuid"] == "GPU-v100"
    gpuassign.save({"allowed": ["GPU-3060"]})                                           # the V100 is taken away: the choice for rendering goes with it
    assert browser_gpu.nvidia_render_device()["uuid"] == "GPU-3060"


def _fake_hyperframes(monkeypatch):
    from vt.render import hyperframes

    calls = []

    def fake_run(cmd, on_line=None, stall_seconds=None, **kw):
        calls.append(list(cmd))
        if cmd and cmd[0] == "render":                                                  # a finished video; the snapshot command leaves a folder of pictures, which this does not make
            open(cmd[cmd.index("-o") + 1], "wb").write(b"x")

    monkeypatch.setattr(hyperframes, "run", fake_run)
    monkeypatch.setattr(hyperframes, "hyperframes_cmd", lambda *a: list(a))
    return hyperframes, calls


def test_rendering_uses_the_graphics_card_only_when_one_is_allowed(box, monkeypatch, tmp_path):
    from vt.render import browser_gpu

    hyperframes, calls = _fake_hyperframes(monkeypatch)
    monkeypatch.setattr(browser_gpu, "nvidia_render_device", lambda: {"name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060"})
    gpuassign.save({"allowed": ["GPU-3060"]})
    hyperframes.render_silent(tmp_path / "comp", tmp_path / "a.mp4")
    assert "--gpu" in calls[-1] and "--browser-gpu" in calls[-1]
    gpuassign.save({"allowed": []})
    out = tmp_path / "b.mp4"
    hyperframes.render_silent(tmp_path / "comp", out)
    assert "--gpu" not in calls[-1] and "--no-browser-gpu" in calls[-1]
    import json

    report = json.loads(out.with_suffix(".acceleration.json").read_text(encoding="utf-8"))
    assert report["gpu_requested"] is False and "no graphics card" in report["warnings"][0]
    hyperframes.snapshot(tmp_path / "comp", tmp_path / "frames", [1.0])
    assert "--browser-gpu" not in calls[-1]


# ----------------------------------------------------------------------------------------------------------------------------------- the encoder
def test_the_hardware_encoder_follows_the_list_and_the_render_card(box, monkeypatch):
    monkeypatch.setattr(gpu, "_nvenc_cache", True)
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpu.has_nvenc() and gpu.nvenc_device() == ["-gpu", "1"]                      # the process still sees both cards: NVENC counts the 3060 as 1
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060")
    assert gpu.nvenc_device() == ["-gpu", "0"]                                          # fenced to it: 0
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    gpuassign.save({"allowed": []})
    assert not gpu.has_nvenc() and gpu.nvenc_device() == []                             # no card: the processor encodes


def test_the_final_mix_uses_the_hardware_encoder_on_the_chosen_card_or_the_processor(box, monkeypatch, tmp_path):
    from vt.render import mux

    seen = []
    monkeypatch.setattr(mux, "find_tool", lambda name: name)
    monkeypatch.setattr(mux, "_measure", lambda *a, **k: None)
    monkeypatch.setattr(mux, "run", lambda cmd, **k: seen.append(list(cmd)))
    gpuassign.save({"allowed": ["GPU-3060"]})
    mux.mix_and_mux(tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4", duration=5.0, short_side=720, gpu=True)
    assert "h264_nvenc" in seen[-1] and seen[-1][seen[-1].index("-gpu") + 1] == "1"
    gpuassign.save({"allowed": []})
    mux.mix_and_mux(tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4", duration=5.0, short_side=720, gpu=True)
    assert "h264_nvenc" not in seen[-1] and "libx264" in seen[-1] and "-gpu" not in seen[-1]


# ----------------------------------------------------------------------------------------------------------------------------------- speech and the models
def test_speech_recognition_listens_on_the_processor_when_no_card_is_allowed(box, monkeypatch):
    from vt.stages import asr

    monkeypatch.setattr(gpu, "prepare", lambda: None)
    fake = SimpleNamespace(get_cuda_device_count=lambda: 2)
    monkeypatch.setitem(__import__("sys").modules, "ctranslate2", fake)
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert asr.cuda_available() is True
    gpuassign.save({"allowed": []})
    assert asr.cuda_available() is False


def test_the_voice_and_cutout_models_get_no_cuda_provider_when_no_card_is_allowed(box, monkeypatch):
    ort = pytest.importorskip("onnxruntime")
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])
    gpuassign.save({"allowed": ["GPU-3060"]})
    first = gpu.onnx_providers()[0]
    assert first == ("CUDAExecutionProvider", {"device_id": 1})
    gpuassign.save({"allowed": []})
    assert gpu.onnx_providers() == ["CPUExecutionProvider"] and not gpu.cuda_for_onnx()


def test_the_torch_models_use_the_chosen_card_or_the_processor(box, monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpu.torch_device() == "cuda:1"
    gpuassign.save({"allowed": []})
    assert gpu.torch_device() == "cpu"
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    gpuassign.save({"allowed": "all"})
    assert gpu.torch_device() == "cpu"


# ----------------------------------------------------------------------------------------------------------------------------------- the System panel, and the programs of ours that are started on a card
def test_the_system_panel_calls_a_card_usable_by_the_same_list(box):
    rows = [{"index": c["index"], "name": c["name"], "uuid": c["uuid"], "memory_total_gb": c["total_gb"], "memory_used_gb": c["total_gb"] - c["free_gb"], "percent": c["load"]} for c in box.cards]
    programs = {c["uuid"]: [] for c in box.cards}
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert sysstats._visible(rows, programs) == {"GPU-3060"}


def test_a_program_of_ours_started_on_a_chosen_number_can_only_reach_an_allowed_card(box):
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert gpuassign.uuid_for(1) == "GPU-3060" and gpuassign.uuid_for("1") == "GPU-3060"
    assert gpuassign.uuid_for(0) is None and gpuassign.uuid_for("x") is None and gpuassign.uuid_for(None) is None
    assert gpuassign.child_env(1) == {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": "GPU-3060"}
    assert gpuassign.child_env(0) == {}                                                 # the V100: it keeps the fence it inherits, nothing more


def test_the_picture_engine_starts_on_an_allowed_card_only(box, monkeypatch, tmp_path):
    from vt.engines import installers

    started = []
    monkeypatch.setattr(installers.subprocess, "Popen", lambda cmd, **kw: started.append(kw["env"]))
    gpuassign.save({"allowed": ["GPU-3060"]})
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060")                              # what the server's own fence is
    installers.ComfyInstaller(root=tmp_path / "comfy", gpu=0).start()
    assert started[-1]["CUDA_VISIBLE_DEVICES"] == "GPU-3060"                            # card 0 is the V100: not used, the inherited fence stays
    installers.ComfyInstaller(root=tmp_path / "comfy", gpu=1).start()
    assert started[-1]["CUDA_VISIBLE_DEVICES"] == "GPU-3060"


def test_the_language_model_starts_on_an_allowed_card_only(box, monkeypatch):
    from vt import llm

    started = []
    up = {"yes": False}
    monkeypatch.setattr(llm, "reachable", lambda url: up["yes"])
    monkeypatch.setattr(llm, "binary", lambda *a: "ollama")
    monkeypatch.setattr(llm, "is_local", lambda url: True)
    monkeypatch.setattr(llm.subprocess, "Popen", lambda cmd, **kw: (started.append(kw["env"]), up.update(yes=True)))
    gpuassign.save({"allowed": ["GPU-3060"]})
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-3060")
    assert llm.start_server("http://127.0.0.1:11444", wait=2, gpu=0)
    assert started[-1]["CUDA_VISIBLE_DEVICES"] == "GPU-3060"
    up["yes"] = False
    assert llm.start_server("http://127.0.0.1:11444", wait=2, gpu=1)
    assert started[-1]["CUDA_VISIBLE_DEVICES"] == "GPU-3060"


def test_the_engine_setup_recommends_only_among_allowed_cards(box):
    from vt.engines import setup

    hw = {"gpus": [{"index": 0, "compute": 9.0}, {"index": 1, "compute": 8.6}]}
    gpuassign.save({"allowed": "all"})
    assert setup._recommended_gpu(hw) == 0
    gpuassign.save({"allowed": ["GPU-3060"]})
    assert setup._recommended_gpu(hw) == 1
    gpuassign.save({"allowed": []})
    assert setup._recommended_gpu(hw) is None
