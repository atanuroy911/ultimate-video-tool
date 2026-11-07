"""Security checks use temporary files and fake credentials; no model or media runs."""
import io
import json
import zipfile

import pytest

from vt.ai import talk
from vt.modules.calls import append_call, append_technical, read_calls, read_technical, redact


@pytest.fixture(autouse=True)
def private_data(tmp_path, monkeypatch):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)


@pytest.mark.parametrize("text", [
    'Authorization: Bearer private-credential-here',
    'authorization="Basic private-credential-here"',
    '{"api_key": "private-credential-here", "message": "keep this"}',
    'accessToken=private-credential-here',
    'https://example.test/?token=private-credential-here&format=json',
    'https://user:private-credential-here@example.test/api',
    'Cookie: vt_token=private-credential-here; Path=/',
    'password="private-credential-here with spaces"',
])
def test_credentials_in_diagnostic_text_are_hidden(text):
    safe = redact(text)
    assert "private-credential-here" not in safe
    assert "[redacted]" in safe


def test_secret_fields_are_hidden_without_removing_normal_model_metadata():
    from vt.modules.calls import is_secret_key

    value = {"apiKey": "private-api", "nested": [{"refresh_token": "private-refresh"}],
             "max_tokens": 500, "token_count": 24, "token_usage": {"input": 24},
             "has_key": True, "openai_key_set": True, "sentence": "Keep the title above Maya."}
    safe = redact(value)
    assert safe["apiKey"] == "[redacted]"
    assert safe["nested"][0]["refresh_token"] == "[redacted]"
    for name in ("max_tokens", "token_count", "token_usage", "has_key", "openai_key_set", "sentence"):
        assert safe[name] == value[name]
        assert not is_secret_key(name)
    assert value["apiKey"] == "private-api", "logging must not change the director's actual input"


def test_configured_keys_are_hidden_even_when_repeated_without_a_label(tmp_path, monkeypatch):
    from vt import paths
    from vt.util import write_json

    secrets = ["configured-openai-key", "configured-engine-key", "configured-hub-key", "env-secret-value"]
    write_json(paths.SETTINGS, {"openai_key": secrets[0], "engines": {"ollama": {"key": secrets[1]}}})
    write_json(tmp_path / "engine-hub.json", {"key": secrets[2]})
    monkeypatch.setenv("GPU_PASS", secrets[3])
    safe = redact("A provider failed: " + " / ".join(secrets))
    assert all(secret not in safe for secret in secrets)
    assert "A provider failed" in safe


def test_runtime_server_key_and_url_encoded_credentials_are_hidden(monkeypatch):
    from urllib.parse import quote, quote_plus
    from vt.server import serve

    secret = "a-server-key/with spaces+reserved"
    monkeypatch.setitem(serve.STATE, "key", secret)
    safe = redact(" / ".join((secret, quote(secret, safe=""), quote_plus(secret, safe=""))))
    assert safe == "[redacted] / [redacted] / [redacted]"


def test_retired_director_tokens_remain_hidden_without_a_label():
    from vt.mcp import scope

    token = scope.issue("security-log")
    scope.revoke(token)
    assert redact("The tool repeated " + token) == "The tool repeated [redacted]"


def test_job_logs_and_public_results_hide_credentials():
    from vt.server.jobs import Job

    job = Job("test", "plan", "video", "Make video", msg="Authorization: Bearer private-progress",
              error="token=private-error", result={"apiKey": "private-result", "decision": "Keep every title"})
    job.add("warning", "password=private-log")
    assert "private-" not in json.dumps(job.lines)
    assert "private-" not in json.dumps(job.public())
    assert job.public()["result"]["decision"] == "Keep every title"
    assert job.result["apiKey"] == "private-result"
    job.lines.append({"n": 2, "text": "Authorization: Bearer private-legacy"})
    assert "private-" not in json.dumps(job.log_after())


def test_settings_projection_hides_nested_credentials_and_keeps_presence_flags():
    from vt.server.app import _public_settings

    original = {"openai_key": "private-openai", "mcp_token": "private-mcp", "password": "private-password",
                "oauth": {"clientSecret": "private-client", "refresh_token": "private-refresh", "enabled": True},
                "engines": {"ollama": {"mode": "remote", "url": "http://box:9000/?token=private-url", "key": "private-engine"}},
                "token_count": 15, "has_key": True}
    result = _public_settings(original)
    assert "private-" not in json.dumps(result)
    assert all(name not in result for name in ("openai_key", "mcp_token", "password"))
    assert result["oauth"] == {"enabled": True}
    assert result["stock_keys"]["openai"] is True
    assert result["engines"]["ollama"]["has_key"] is True
    assert result["token_count"] == 15 and result["has_key"] is True


@pytest.fixture()
def project(projects_dir):
    from vt.project import Project

    folder = projects_dir / "security-log"
    folder.mkdir()
    (folder / "project.json").write_text("{}", encoding="utf-8")
    return Project(folder.name)


def test_conversation_disk_and_details_hide_secrets_but_preserve_the_direction(project):
    from vt.server.log_routes import ai_talk, ai_talk_row

    talk.record("claude", "sonnet", system='Authorization: Bearer private-system',
                prompt={"instructions": "Keep every title", "apiKey": "private-prompt"},
                answer='{"token": "private-answer", "decision": "Keep Maya"}',
                error="GET https://example.test/?token=private-error", folder=project.dir)
    disk = (project.dir / talk.FILE).read_text(encoding="utf-8")
    assert "private-" not in disk
    detail = ai_talk_row(project.id, 0)
    assert json.loads(detail["prompt"])["instructions"] == "Keep every title"
    assert json.loads(detail["answer"])["decision"] == "Keep Maya"
    assert "private-" not in json.dumps(ai_talk(project.id))


def test_legacy_conversations_are_redacted_when_read(project):
    row = {"system": "api_key=private-system", "prompt": "token=private-prompt",
           "answer": "Authorization: Bearer private-answer", "error": "password=private-error"}
    (project.dir / talk.FILE).write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert "private-" not in json.dumps(talk.load(project.dir))


def test_legacy_call_logs_and_downloads_are_redacted(project):
    from vt.server.log_routes import download

    (project.dir / "calls.jsonl").write_text(json.dumps({"seq": 1, "token": "private-call",
                                                       "plain": json.dumps({"token": "private-nested"})}) + "\n", encoding="utf-8")
    (project.dir / "technical.log").write_text("Authorization: Bearer private-technical\n", encoding="utf-8")
    assert "private-" not in json.dumps(read_calls(project.dir))
    assert "private-" not in read_technical(project.dir)
    archive = zipfile.ZipFile(io.BytesIO(download(project.id).body))
    assert all(b"private-" not in archive.read(name) for name in archive.namelist())


def test_call_writes_and_technical_tail_do_not_keep_secrets(tmp_path):
    append_call(tmp_path, {"module": "plan", "plain": 'token="private-call"', "apiKey": "private-key"})
    append_technical(tmp_path, "Authorization: Bearer private-header\nKeep this problem visible")
    assert "private-" not in (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    assert "private-" not in (tmp_path / "technical.log").read_text(encoding="utf-8")
    assert "Keep this problem visible" in read_technical(tmp_path)


def test_invalid_mcp_project_cannot_write_a_conversation_outside_the_project_store(projects_dir):
    from vt.mcp import server

    outside = projects_dir.parent / "outside"
    outside.mkdir()
    (outside / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid project"):
        server.get_transcript("../outside")
    assert not (outside / talk.FILE).exists()


@pytest.mark.parametrize("pid", ["../outside", r"..\outside", ".", "..", "/outside", r"C:\outside"])
def test_mcp_project_paths_cannot_escape_the_store(projects_dir, pid):
    from vt.mcp.server import _proj

    with pytest.raises(ValueError, match="invalid project"):
        _proj(pid)


def test_details_project_resolving_outside_the_store_is_refused(project, projects_dir, monkeypatch):
    from pathlib import Path
    from fastapi import HTTPException
    from vt.server.modules_routes import project_or_404

    # Model the resolution of a junction without requiring Windows symlink privileges.
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        projects_dir.parent / "outside" if path == project.dir else original(path, *args, **kwargs))
    with pytest.raises(HTTPException) as error:
        project_or_404(project.id)
    assert error.value.status_code == 400


@pytest.mark.parametrize("filename", ["calls.jsonl", "technical.log", "ai_talk.jsonl"])
def test_log_leaf_resolving_outside_project_is_neither_read_nor_overwritten(project, monkeypatch, filename):
    from pathlib import Path
    from vt.server.log_routes import download

    file = project.dir / filename
    original_text = json.dumps({"seq": 1, "system": "", "prompt": "outside-confidential-marker",
                                "answer": "", "kind": "ask"}) + "\n"
    file.write_text(original_text, encoding="utf-8")
    original_resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        project.dir.parent.parent / filename if path == file else original_resolve(path, *args, **kwargs))
    if filename == "calls.jsonl":
        assert read_calls(project.dir) == []
        with pytest.raises(ValueError, match="project"):
            append_call(project.dir, {"plain": "Should not be written"})
    elif filename == "technical.log":
        assert read_technical(project.dir) == ""
        with pytest.raises(ValueError, match="project"):
            append_technical(project.dir, "Should not be written")
    else:
        assert talk.load(project.dir) == []
        talk.record("test", "fake", prompt="Should not be written", folder=project.dir)
    assert file.read_text(encoding="utf-8") == original_text
    archive = zipfile.ZipFile(io.BytesIO(download(project.id).body))
    assert all(b"outside-confidential-marker" not in archive.read(name) for name in archive.namelist())


def test_ai_image_parent_cannot_redirect_a_write_outside_project(project, monkeypatch):
    from pathlib import Path

    image_dir = project.dir / "ai-talk-images"
    original_resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        project.dir.parent.parent / "outside-image" if path == image_dir or path.parent == image_dir
                        else original_resolve(path, *args, **kwargs))
    talk.record("test", "fake", prompt="Keep this visible", answer="Keep the direction", images=1,
                image_data=[b"\x89PNG\r\n\x1a\nfake-test-picture"], folder=project.dir)
    assert not image_dir.exists()
    row = talk.load(project.dir)[0]
    assert row["answer"] == "Keep the direction"
    assert "image_files" not in row and "storage" in row["image_save_error"]


def test_windows_reparse_log_is_refused_even_if_it_resolves_inside_project(project, monkeypatch):
    import stat
    from pathlib import Path
    from types import SimpleNamespace
    from vt.secure_paths import project_file

    file = project.dir / "technical.log"
    file.write_text("private marker", encoding="utf-8")
    original_lstat = Path.lstat
    monkeypatch.setattr(Path, "lstat", lambda path:
                        SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
                        if path == file else original_lstat(path))
    with pytest.raises(ValueError, match="project"):
        project_file(project.dir, "technical.log")
