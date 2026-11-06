import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'server'))
sys.path.insert(0, str(ROOT / "samples"))


import os

os.environ.setdefault("VT_TRANSLATE", "0")   # tests never touch the network
os.environ.setdefault("VT_LAYOUT_CHECK", "0")   # nor open a composition in a browser to read the layout guard (the tests that want it turn it on)


@pytest.fixture(autouse=True)
def _no_local_ai_by_default(monkeypatch):
    """Tests never talk to a real model (or download one): the local AI is off unless a test turns it on itself."""
    from vt import llm

    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "off", "ollama_url": "http://127.0.0.1:9", "ollama_model": "", "llm_auto_download": False})
    from vt.ai import providers

    monkeypatch.setattr(providers, "find_claude", lambda: None)      # nor the Claude login of the computer running them


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """No test reads or writes the real settings.json (it holds the owner's keys and choices): each test gets an empty one."""
    from vt import paths

    f = tmp_path / "settings.json"
    f.write_text('{"autopilot": false}', encoding="utf-8")      # autopilot would render a real video after every pipeline run; tests opt in
    monkeypatch.setattr(paths, "SETTINGS", f)
    monkeypatch.setattr(paths, "GLOBAL_GLOSSARY", tmp_path / "glossary.json")     # learned spellings and taste are the owner's too
    from vt import taste

    monkeypatch.setattr(taste, "_path", lambda: tmp_path / "taste.json")
    from vt.ai import providers

    monkeypatch.setattr(providers, "_cache_dir", lambda: tmp_path / "ai_cache")      # saved AI answers: a test must not read what an earlier run saved, nor leave any behind
    from vt import directors

    monkeypatch.setattr(directors, "_seen_path", lambda: tmp_path / "directors-seen.json")     # the computers that were connected
    try:
        import vt.server.app as A

        monkeypatch.setattr(A, "SETTINGS_PATH", f)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _no_real_graphics_cards(monkeypatch):
    """Which cards Video Tool may use (vt/gpuassign.py) is read from the machine's own cards, so a test would depend on the machine (and ask nvidia-smi again and again).
    By default a test sees a computer with no NVIDIA card, where nothing is forbidden; a test about cards gives its own."""
    from vt import gpuassign

    monkeypatch.setattr(gpuassign, "_cards", lambda: [])
    monkeypatch.setattr(gpuassign, "_PIN", None)
    monkeypatch.setattr(gpuassign, "_APPLIED", None)
    monkeypatch.setattr(gpuassign, "_memo", {})
    monkeypatch.setattr(gpuassign, "MEMO_SECONDS", -1.0)                            # what nvidia-smi says is not remembered: a test changes its fake cards and programs as it goes


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: renders real frames with HyperFrames (needs Node + Chrome)")


@pytest.fixture()
def projects_dir(tmp_path, monkeypatch):
    """Point the project store at a temp folder so tests never touch real projects."""
    from vt import paths

    import shutil

    d = tmp_path / "projects"
    d.mkdir()
    monkeypatch.setattr(paths, "PROJECTS", d)
    themes = tmp_path / "themes"                       # themes made during a test (automatic designs, saves) stay in the temp folder
    shutil.copytree(paths.BUILTIN_THEMES_DIR, themes, ignore=shutil.ignore_patterns("auto-*"))
    monkeypatch.setattr(paths, "THEMES", themes)
    return d


@pytest.fixture()
def ref(projects_dir):
    """The hand-written Banglish reference project (synthetic word timings, silent wav)."""
    import build_reference

    build_reference.main("reference")
    from vt.project import Project

    return Project("reference")
