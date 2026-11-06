"""The setup question in a terminal (PLAN-PERFECT K5): `vt gpu setup`, `vt gpu allow`, `vt server --gpus`, which the install scripts and Docker call.
A fake `nvidia-smi` on the path answers the questions the real one does, so the whole chain runs: the listing of cards, what is using each, the saved answer and the fence."""
import json
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vt import gpuassign, paths, sysstats

REAL_CARDS = gpuassign._cards                                    # read before the test configuration swaps it out for "no card"

SMI = r'''
import json, os, sys

cfg = json.load(open(os.environ["FAKE_SMI_CONFIG"], encoding="utf-8"))
cards, apps = cfg["cards"], cfg.get("apps", [])
args = sys.argv[1:]
if args and args[0] == "pmon":
    print("# gpu         pid   type     sm    mem    enc    dec    jpg    ofa     fb   ccpm    command")
    print("# Idx           #    C/G      %      %      %      %      %      %     MB     MB    name")
    for a in apps:
        print(f"    {a['gpu']}   {a['pid']}     C     {a.get('sm', 50)}     40      -      -      -      -   {a['mb']}      0    {a['name']}")
elif any(x.startswith("--query-compute-apps") for x in args):
    for a in apps:
        print(f"{cards[a['gpu']]['uuid']}, {a['pid']}, {a['name']}, {a['mb']}")
elif any(x.startswith("--query-gpu=index,name,uuid,memory.free") for x in args):
    for c in cards:
        print(f"{c['index']}, {c['name']}, {c['uuid']}, {c['free_mb']}, {c['total_mb']}, {c.get('util', 0)}")
elif any(x.startswith("--query-gpu=") for x in args):
    for c in cards:
        used = c["total_mb"] - c["free_mb"]
        print(f"{c['index']}, {c['name']}, {c['uuid']}, {c.get('util', 0)}, 10, {used}, {c['total_mb']}, 50, 30.0, 170.0, 1500, 0")
'''
V100 = {"index": 0, "name": "Tesla V100-PCIE-16GB", "uuid": "GPU-v100", "free_mb": 6400, "total_mb": 16384, "util": 90}
RTX = {"index": 1, "name": "NVIDIA GeForce RTX 3060", "uuid": "GPU-3060", "free_mb": 11500, "total_mb": 12288, "util": 3}
TRAINING = {"gpu": 0, "pid": 4321, "name": "python3", "mb": 9934, "sm": 90}


class Smi:
    """The cards and programs the fake nvidia-smi reports; `save()` makes the next run of it say so."""

    def __init__(self, config: Path):
        self.config, self.cards, self.apps = config, [V100, RTX], [TRAINING]
        self.save()

    def save(self):
        self.config.write_text(json.dumps({"cards": self.cards, "apps": self.apps}), encoding="utf-8")


@pytest.fixture()
def smi(tmp_path, monkeypatch):
    """A fake nvidia-smi on the path (the real code finds it the way it finds the real one)."""
    folder = tmp_path / "bin"
    folder.mkdir()
    script = folder / "fake_smi.py"
    script.write_text(SMI, encoding="utf-8")
    box = Smi(tmp_path / "smi.json")
    if os.name == "nt":
        (folder / "nvidia-smi.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = folder / "nvidia-smi"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(folder) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_SMI_CONFIG", str(box.config))
    monkeypatch.setattr(gpuassign, "_cards", REAL_CARDS)
    monkeypatch.setattr(gpuassign, "_memo", {})
    monkeypatch.setattr(gpuassign, "MEMO_SECONDS", 2.0)                                   # the real thing: what nvidia-smi says is kept for two seconds
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    monkeypatch.setattr(sysstats, "_gpu_cache", {"at": 0, "value": None})                 # nothing from an earlier test
    return box


def run(*args, input=None):
    from vt.cli import app

    return CliRunner().invoke(app, list(args), input=input)


def test_the_fake_card_listing_is_read_by_the_real_code(smi):
    cards = gpuassign._cards()
    assert [c["name"] for c in cards] == ["Tesla V100-PCIE-16GB", "NVIDIA GeForce RTX 3060"] and cards[1]["free_gb"] == 11.2
    d = gpuassign.describe()
    assert d["cards"][0]["using"] == [{"label": "python3", "gb": 9.7, "ours": False}] and d["cards"][1]["using"] == []


def test_one_card_has_nothing_to_ask(smi):
    smi.cards, smi.apps = [RTX], []
    smi.save()
    out = run("gpu", "setup", "--ask")                                                    # even when asked to ask: there is nothing to choose between
    assert out.exit_code == 0 and "Video Tool may use: 1 NVIDIA GeForce RTX 3060." in out.output
    assert "Which may Video Tool use" not in out.output and "Nobody has chosen" not in out.output
    assert gpuassign.saved_allowed() is None


def test_nobody_there_keeps_the_one_card_default_and_says_how_to_change_it(smi):
    out = run("gpu", "setup")                                                             # no terminal: nobody to ask
    assert out.exit_code == 0 and "Video Tool may use: 1 NVIDIA GeForce RTX 3060." in out.output          # the card nobody else works on, not the V100 with the training
    assert "Nobody has chosen, so it uses this one card only" in out.output and "vt gpu allow" in out.output
    assert gpuassign.saved_allowed() is None and gpuassign.needs_choice()


def test_a_person_there_is_asked_and_the_answer_is_saved(smi):
    out = run("gpu", "setup", "--ask", input="1\n")
    assert out.exit_code == 0 and "This computer has more than one graphics card" in out.output
    assert "python3 9.7 GB" in out.output and "Which may Video Tool use?" in out.output           # what is using the V100 is shown before the question
    assert "Video Tool may use: 1 NVIDIA GeForce RTX 3060." in out.output and "Nobody has chosen" not in out.output
    assert gpuassign.saved_allowed() == ["GPU-3060"] and not gpuassign.needs_choice()
    again = run("gpu", "setup", "--ask")                                                  # answered: it does not ask again
    assert "Which may Video Tool use?" not in again.output and "Video Tool may use: 1 NVIDIA GeForce RTX 3060." in again.output


def test_pressing_enter_keeps_the_safe_default(smi):
    out = run("gpu", "setup", "--ask", input="\n")
    assert out.exit_code == 0 and "Nobody has chosen" in out.output and gpuassign.saved_allowed() is None


def test_the_answer_can_be_all_none_or_a_list(smi):
    assert "0 Tesla V100-PCIE-16GB, 1 NVIDIA GeForce RTX 3060" in run("gpu", "setup", "--ask", input="all\n").output
    assert gpuassign.saved_allowed() == ["GPU-v100", "GPU-3060"]
    assert "no card (the processor does everything)" in run("gpu", "setup", "--ask", "--gpus", "none").output
    assert gpuassign.saved_allowed() == []
    assert run("gpu", "setup", "--gpus", "0 1").exit_code == 0 and gpuassign.saved_allowed() == ["GPU-v100", "GPU-3060"]
    assert run("gpu", "setup", "--gpus", "1,0").exit_code == 0 and gpuassign.saved_allowed() == ["GPU-v100", "GPU-3060"]


def test_a_wrong_answer_is_refused_with_a_sentence_and_nothing_changes(smi):
    run("gpu", "setup", "--gpus", "1")
    bad = run("gpu", "setup", "--gpus", "7")
    assert bad.exit_code != 0 and "not a card" in bad.output.replace("\n", " ") and gpuassign.saved_allowed() == ["GPU-3060"]
    paths.SETTINGS.write_text("{}", encoding="utf-8")                                     # nobody has answered again
    bad = run("gpu", "setup", "--ask", input="seven\n")                                    # a word that is not a card, typed at the question
    assert bad.exit_code != 0 and "not a card" in bad.output.replace("\n", " ") and gpuassign.saved_allowed() is None


def test_no_nvidia_card_at_all_is_said_plainly(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))                                              # no nvidia-smi anywhere
    monkeypatch.setattr(gpuassign, "_cards", REAL_CARDS)
    monkeypatch.setattr(gpuassign, "_memo", {})
    monkeypatch.setattr(paths, "SETTINGS", tmp_path / "settings.json")
    out = run("gpu", "setup")
    assert out.exit_code == 0 and "No NVIDIA graphics card here: the processor does everything." in out.output


def test_the_server_command_takes_the_cards_and_fences_itself_to_them(smi, monkeypatch):
    import typer

    from vt import cli
    from vt.engines import placement

    monkeypatch.setattr(cli, "_fenced", False)
    monkeypatch.setattr(cli, "_first_run_comfy", lambda: "")
    monkeypatch.setattr(placement, "place", lambda *a, **k: (_ for _ in ()).throw(typer.Exit(0)))      # stop where the engines would start
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "unset-by-the-test")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    out = run("server", "--gpus", "1", "--port", "8799")
    assert out.exit_code == 0 and gpuassign.saved_allowed() == ["GPU-3060"]
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "GPU-3060" and "Graphics cards Video Tool may use: 1 NVIDIA GeForce RTX 3060" in out.output
    monkeypatch.setattr(cli, "_fenced", False)
    bad = run("server", "--gpus", "5")
    assert bad.exit_code != 0 and gpuassign.saved_allowed() == ["GPU-3060"]                # a wrong card stops the server before it starts anything


def test_a_reading_of_the_cards_asks_nvidia_smi_a_handful_of_times_not_hundreds(smi, monkeypatch):
    """The default card depends on what works on each card, and the System panel's reading depends on the default: the two must not ask each other (they once did, 534 calls)."""
    import subprocess

    calls = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1])
    for name, ask, most in (("describe", gpuassign.describe, 5), ("apply", gpuassign.apply, 5), ("blocked", gpuassign.blocked, 5), ("restart_needed", gpuassign.restart_needed, 5),
                            ("resolve", lambda: gpuassign.resolve("render"), 5), ("job_env", lambda: gpuassign.job_env("ai"), 5), ("the System panel's cards", sysstats._gpus, 3)):
        calls.clear()
        gpuassign._memo.clear()
        sysstats._gpu_cache.update(at=0, value=None)
        ask()
        assert len(calls) <= most, f"{name} asked nvidia-smi {len(calls)} times"


def test_what_nvidia_smi_says_is_asked_for_once_every_couple_of_seconds(smi, monkeypatch):
    import subprocess

    calls = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1])
    first = gpuassign._cards()
    assert len(calls) == 1 and [c["index"] for c in first] == [0, 1]
    first[0]["name"] = "changed by the caller"                                            # what is handed out is a copy
    assert gpuassign._cards()[0]["name"] == "Tesla V100-PCIE-16GB" and len(calls) == 1
    gpuassign._memo["cards"] = (0.0, gpuassign._memo["cards"][1])                         # two seconds later
    gpuassign._cards()
    assert len(calls) == 2
    smi.cards = []
    smi.save()
    gpuassign._memo.clear()
    assert gpuassign._cards() == [] and gpuassign._cards() == [] and len(calls) == 4      # an empty answer (a failed question) is asked again at once, never kept


def test_the_system_panel_marks_the_default_card_usable_and_the_one_with_the_training_not(smi):
    rows = sysstats._gpus()
    assert [(g["index"], g["usable_by_video_tool"]) for g in rows] == [(0, False), (1, True)]
    assert rows[0]["programs"][0]["label"] == "python3" and rows[0]["programs"][0]["gb"] == 9.7
    run("gpu", "setup", "--gpus", "all")
    gpuassign._memo.clear()
    sysstats._gpu_cache.update(at=0, value=None)
    assert [g["usable_by_video_tool"] for g in sysstats._gpus()] == [True, True]
    run("gpu", "setup", "--gpus", "none")
    sysstats._gpu_cache.update(at=0, value=None)
    assert [g["usable_by_video_tool"] for g in sysstats._gpus()] == [False, False]
