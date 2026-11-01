"""Moving a developer checkout's data into the per-user folder: copy only, never overwrite, never delete, models linked."""
import os

import pytest

from vt import migrate as MG


@pytest.fixture()
def old(tmp_path):
    o = tmp_path / "old"
    (o / "projects" / "p1").mkdir(parents=True)
    (o / "projects" / "p1" / "project.json").write_text('{"id": "p1"}', encoding="utf-8")
    (o / "projects" / "p1" / "media").mkdir()
    (o / "projects" / "p1" / "media" / "a.png").write_bytes(b"png")
    (o / "voices" / "me").mkdir(parents=True)
    (o / "voices" / "me" / "voice.json").write_text("{}", encoding="utf-8")
    (o / "models" / "kokoro").mkdir(parents=True)
    (o / "models" / "kokoro" / "m.onnx").write_bytes(b"x" * 1000)
    (o / "settings.json").write_text('{"k": 1}', encoding="utf-8")
    (o / "assets" / "music" / "user").mkdir(parents=True)
    (o / "assets" / "music" / "user" / "song.mp3").write_bytes(b"mp3")
    return o


def test_a_plan_only_looks(old, tmp_path):
    new = tmp_path / "new"
    r = MG.plan(old, new)
    assert {i.name for i in r.items} == {"projects", "voices", "settings.json", "assets/music/user", "models"}
    assert next(i for i in r.items if i.name == "projects").files == 2
    assert not new.exists()                                                       # nothing was created
    assert {i.name for i in MG.plan(old, new, models=False).items} == {"projects", "voices", "settings.json", "assets/music/user"}
    with pytest.raises(ValueError):
        MG.plan(old, old)


def test_everything_is_copied_models_are_linked_and_the_old_folder_is_untouched(old, tmp_path):
    new = tmp_path / "new"
    before = sorted(str(p.relative_to(old)) for p in old.rglob("*"))
    r = MG.run(old, new)
    assert not r.errors and r.copied + r.linked == 6
    assert (new / "projects" / "p1" / "media" / "a.png").read_bytes() == b"png"
    assert (new / "user-music" / "song.mp3").read_bytes() == b"mp3" and (new / "settings.json").read_text(encoding="utf-8") == '{"k": 1}'
    assert (new / "models" / "kokoro" / "m.onnx").stat().st_size == 1000
    assert r.linked == 1 and os.path.samefile(old / "models" / "kokoro" / "m.onnx", new / "models" / "kokoro" / "m.onnx")     # same disk: no second copy
    assert sorted(str(p.relative_to(old)) for p in old.rglob("*")) == before        # the old folder is as it was


def test_running_twice_and_existing_files_are_never_overwritten(old, tmp_path):
    new = tmp_path / "new"
    (new / "projects" / "p1").mkdir(parents=True)
    (new / "projects" / "p1" / "project.json").write_text('{"id": "mine"}', encoding="utf-8")
    r = MG.run(old, new)
    assert r.skipped == 1 and (new / "projects" / "p1" / "project.json").read_text(encoding="utf-8") == '{"id": "mine"}'
    r2 = MG.run(old, new)
    assert r2.copied == 0 and r2.linked == 0 and r2.skipped == 6


def test_the_command_is_a_dry_run_unless_asked(old, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from vt import cli, paths

    new = tmp_path / "new"
    monkeypatch.setattr(paths, "DATA", new)
    out = CliRunner().invoke(cli.app, ["migrate", "--from", str(old)])
    assert out.exit_code == 0 and "dry run" in out.stdout and not new.exists()
    out = CliRunner().invoke(cli.app, ["migrate", "--from", str(old), "--yes", "--no-models"])
    assert out.exit_code == 0 and (new / "projects" / "p1" / "project.json").exists() and not (new / "models").exists()
    assert CliRunner().invoke(cli.app, ["migrate", "--from", str(tmp_path / "nope")]).exit_code != 0
