"""The release tooling: one version everywhere, and an Engine package that holds what a server needs and nothing of the Studio."""
import importlib.util
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_one_version_is_written_to_every_file(tmp_path, monkeypatch):
    sv = _load("set_version")
    (tmp_path / "desktop").mkdir()
    (tmp_path / "pyproject.toml").write_bytes(b'[project]\r\nname = "video-tool"\r\nversion = "0.1.0"\r\n')
    (tmp_path / "uv.lock").write_bytes(b'[[package]]\nname = "other"\nversion = "9.9.9"\n\n[[package]]\nname = "video-tool"\nversion = "0.1.0"\nsource = { editable = "." }\n')
    (tmp_path / "desktop" / "package.json").write_bytes(b'{\n  "name": "x",\n  "version": "1.0.0"\n}\n')
    monkeypatch.setattr(sv, "ROOT", tmp_path)
    assert sv.current() == "0.1.0"
    changed = sv.apply("v2.3.4")
    assert set(changed) == {"pyproject.toml", "uv.lock", "desktop/package.json"}
    assert b'version = "2.3.4"\r\n' in (tmp_path / "pyproject.toml").read_bytes()                 # line endings kept
    lock = (tmp_path / "uv.lock").read_text()
    assert 'name = "other"\nversion = "9.9.9"' in lock and 'name = "video-tool"\nversion = "2.3.4"' in lock          # only our own entry
    assert json.loads((tmp_path / "desktop" / "package.json").read_text())["version"] == "2.3.4"
    assert sv.apply("2.3.4") == []                                                                  # nothing to do the second time
    with pytest.raises(SystemExit):
        sv.apply("two point oh")


def test_the_repository_agrees_with_itself_about_the_version():
    sv = _load("set_version")
    assert sv.SEMVER.match(sv.current())


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    mk = _load("make_engine_package")
    out = tmp_path_factory.mktemp("pkg")
    files = mk.collect("1.2.3")
    mk.write_zip(files, out / "e.zip")
    mk.write_tar(files, out / "e.tar.gz")
    return files, out


def test_the_engine_package_has_the_server_and_none_of_the_studio(package):
    files, _ = package
    names = set(files)
    for need in ("vt/cli.py", "vt/engines/hub.py", "vt/engines/server.py", "pyproject.toml", "uv.lock", "install-engine.ps1", "install-engine.sh", "Dockerfile",
                 "docker-compose.yml", "docker-entrypoint.sh", "README-ENGINE.txt", "VERSION", "engine-package.json", "assets/comfy/model-manifest.json"):
        assert f"video-tool-engine/{need}" in names, need
    assert any(n.startswith("video-tool-engine/assets/comfy/workflows/") for n in names)
    top = {n.split("/")[1] for n in names if n.count("/") >= 2}                  # the folders directly inside video-tool-engine/
    assert top == {"vt", "assets"}, top
    assert not any("node_modules" in n or ".venv" in n for n in names)
    assert not any(n.endswith((".pyc", ".mp4", ".safetensors")) for n in names)
    assert files["video-tool-engine/VERSION"] == b"1.2.3\n"
    assert json.loads(files["video-tool-engine/engine-package.json"])["version"] == "1.2.3"


def test_shell_scripts_are_forced_to_unix_line_ends(package):
    files, _ = package
    for n in ("install-engine.sh", "docker-entrypoint.sh", "Dockerfile"):
        assert b"\r" not in files[f"video-tool-engine/{n}"], n


def test_both_archives_hold_the_same_files_and_the_zip_marks_scripts_runnable(package):
    files, out = package
    with zipfile.ZipFile(out / "e.zip") as z:
        assert sorted(z.namelist()) == sorted(files)
        assert z.getinfo("video-tool-engine/install-engine.sh").external_attr >> 16 == 0o755
    with tarfile.open(out / "e.tar.gz") as t:
        assert sorted(t.getnames()) == sorted(files)
        assert t.getmember("video-tool-engine/install-engine.sh").mode == 0o755


def test_the_package_is_small_because_models_and_python_are_fetched_on_the_target(package):
    files, _ = package
    assert sum(len(v) for v in files.values()) < 25_000_000


def test_the_workflows_are_valid_and_wired_together():
    import yaml

    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    rel = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    on = ci.get("on") or ci.get(True)
    assert "workflow_call" in on and "pull_request" in on                       # the release reuses CI, and CI runs on every pull request
    assert {"python", "studio", "docs", "engine-package"} <= set(ci["jobs"])
    jobs = rel["jobs"]
    assert jobs["ci"]["uses"] == "./.github/workflows/ci.yml"
    assert {"app", "engine", "engine-smoke", "engine-image", "publish"} <= set(jobs)
    assert "ci" in jobs["app"]["needs"] and "ci" in jobs["engine"]["needs"]
    assert set(jobs["publish"]["needs"]) >= {"app", "engine", "engine-smoke", "engine-image"}   # nothing is published unless every part built
    assert jobs["publish"]["if"] == "needs.version.outputs.publish == 'true'"
    assert [o for o in jobs["app"]["strategy"]["matrix"]["os"]] == ["windows-latest", "macos-latest", "ubuntu-latest"]


def test_the_scripts_the_workflows_call_exist():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8") + (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    import re

    for rel in set(re.findall(r"(?:python3?|uv run python) (scripts/[\w./-]+\.py)", text)):
        assert (ROOT / rel).is_file(), rel
    for rel in ("packaging/engine/install-engine.sh", "packaging/engine/install-engine.ps1", "studio/package-lock.json", "desktop/package.json", "renderer/scripts/build-fonts.mjs",
                "renderer/scripts/build-icons.mjs"):
        assert (ROOT / rel).is_file(), rel
