"""Autopilot: after the first pipeline run the job renders, watches back and writes the publish kit with no click."""
from pathlib import Path

from vt.util import read_json


def _fake_export(calls):
    def export(p, aspect, progress=None, **kw):
        calls.append(("export", aspect, kw["quality"]))
        p.exports_dir.mkdir(parents=True, exist_ok=True)
        f = p.exports_dir / f"video-{aspect.replace(':', 'x')}.mp4"
        f.write_bytes(b"x")
        progress and progress("render", 1.0)
        return {"video": str(f)}
    return export


def test_autopilot_renders_scores_and_writes_the_kit_once(ref, monkeypatch):
    import vt.server.app as A
    from vt import retention as RT
    from vt.ai import publish
    from vt.project import Project

    calls, said = [], []
    monkeypatch.setattr(A, "export", _fake_export(calls))
    monkeypatch.setattr(RT, "scorecard", lambda *a, **k: calls.append(("score",)) or {"risk": 0.1})
    monkeypatch.setattr(publish, "build_kit", lambda p, cb, cover=True: calls.append(("kit",)))
    p = Project("reference")
    A.autopilot_finish(p, lambda s, f, m="": said.append(s))
    assert [c[0] for c in calls] == ["export", "score", "kit"] and calls[0][1:] == (p.meta().aspect, "looks")
    assert "render" in said and list(p.exports_dir.glob("*.retention.json"))
    A.autopilot_finish(p, lambda *a: None)                       # already exported: a re-run from the editor does not render again
    assert len(calls) == 3


def test_autopilot_names_an_unnamed_video_with_the_ai_title(ref, monkeypatch):
    import vt.server.app as A
    from vt import retention as RT
    from vt.ai import publish
    from vt.project import Project
    from vt.util import write_json

    p = Project("reference")
    p.update_meta(title="Saving money is simple", auto_title=True)
    monkeypatch.setattr(A, "export", _fake_export([]))
    monkeypatch.setattr(RT, "scorecard", lambda *a, **k: {"risk": 0})
    monkeypatch.setattr(publish, "build_kit", lambda p, cb, cover=True: write_json(p.dir / "publish.json", {"title": "Save 10% Every Month"}))
    A.autopilot_finish(p, lambda *a: None)
    assert p.meta().title == "Save 10% Every Month" and not p.meta().auto_title


def test_an_upload_without_a_name_is_named_by_the_file_and_marked_for_the_ai_title(projects_dir, tmp_path):
    import io

    import numpy as np
    import soundfile as sf
    from fastapi.testclient import TestClient

    import vt.server.app as A
    from vt.project import Project

    buf = io.BytesIO()
    sf.write(buf, np.zeros(16000, dtype="float32"), 16000, format="WAV")
    with TestClient(A.app) as c:
        for title in ("", None):                                   # an empty field (the Make screen) and no field at all
            data = {"start": "false"} | ({"title": title} if title is not None else {})
            r = c.post("/api/projects", files={"audio": ("english sample.wav", io.BytesIO(buf.getvalue()))}, data=data)
            meta = Project(r.json()["project"]["id"]).meta()
            assert meta.title == "english sample" and meta.auto_title


def test_autopilot_render_failure_does_not_fail_the_job(ref, monkeypatch):
    import vt.server.app as A
    from vt.project import Project

    def boom(*a, **k):
        raise RuntimeError("no chrome")

    monkeypatch.setattr(A, "export", boom)
    said = []
    A.autopilot_finish(Project("reference"), lambda s, f, m="": said.append(m))
    assert any("Could not render" in m for m in said)


def test_decisions_are_listed_and_can_be_put_back(ref, monkeypatch):
    from fastapi.testclient import TestClient

    import vt.server.app as A
    from vt.project import Project
    from vt.util import write_json

    p = Project("reference")
    write_json(p.dir / "retakes.json", {"cuts": [{"start": 1, "end": 2, "text": "Today I", "reason": "false start, said again right after"}]})
    write_json(p.dir / "tighten.json", {"hash": "x", "target": 60, "cuts": [{"beat": "b3", "text": "As I said", "reason": "a recap the story can do without", "src": [[5, 6]]}]})
    started = []
    monkeypatch.setattr(A, "start_pipeline", lambda p, stage, force, rerender=False: started.append((stage, rerender)) or type("J", (), {"public": lambda self: {"id": "j"}})())
    with TestClient(A.app) as c:
        d = c.get("/api/projects/reference/decisions").json()
        assert d["retakes"][0]["text"] == "Today I" and d["tighten"]["target"] == 60 and "src" not in d["tighten"]["cuts"][0]
        assert c.post("/api/projects/reference/decisions/restore", json={"kind": "tighten"}).status_code == 200
        assert c.post("/api/projects/reference/decisions/restore", json={"kind": "retakes"}).status_code == 200
        assert c.post("/api/projects/reference/decisions/restore", json={"kind": "nope"}).status_code == 422
    m = p.meta().options
    assert m.target_length == "keep" and m.remove_retakes is False and started == [("tighten", True), ("cuts", True)]


def _risky(ref, monkeypatch, risk_after):
    import vt.server.app as A
    from vt import retention as RT
    from vt.ai import providers as AIP
    from vt.project import Project
    from vt.script import chat
    from vt.util import write_json

    p = Project("reference")
    write_json(p.dir / "video_script.json", {"scenes": []})
    before_scenes = p.dir.joinpath("scenes.json").read_text(encoding="utf-8")
    calls = []
    monkeypatch.setattr(AIP, "ai_enabled", lambda: True)
    monkeypatch.setattr(A, "export", _fake_export(calls))
    monkeypatch.setattr(A, "compose_all", lambda p: calls.append(("compose",)))
    monkeypatch.setattr(RT, "scorecard", lambda *a, **k: {"risk": risk_after})

    def talk(p, message, author="person", **k):
        calls.append(("talk", author, message))
        p.dir.joinpath("scenes.json").write_text(before_scenes + " ", encoding="utf-8")          # the director changed the plan
        return {"ok": True, "reply": "Changed 1 of 3 scenes."}
    monkeypatch.setattr(chat, "talk", talk)
    p.exports_dir.mkdir(parents=True, exist_ok=True)
    first = p.exports_dir / "first.mp4"
    first.write_bytes(b"x")
    card = {"risk": 60, "worst": [{"t0": 4.5, "t1": 6.7, "kind": "empty", "severity": 2, "message": "Most of the screen is empty for 2.2 s."}]}
    kept = A.watch_and_revise(p, card, first, lambda *a, **k: None)
    return p, kept, calls, first, before_scenes


def test_watch_and_revise_keeps_a_better_cut(ref, monkeypatch):
    p, kept, calls, first, _ = _risky(ref, monkeypatch, risk_after=20)
    talk = next(c for c in calls if c[0] == "talk")
    assert kept and talk[1] == "viewer test" and "4.5-6.7 s" in talk[2] and not first.exists()
    assert read_json(p.dir / "revise.json") == {"before": 60, "after": 20, "notes": "at 4.5-6.7 s: Most of the screen is empty for 2.2 s.", "kept": True}


def test_watch_and_revise_rolls_back_a_worse_cut(ref, monkeypatch):
    p, kept, calls, first, before = _risky(ref, monkeypatch, risk_after=70)
    assert not kept and first.exists() and p.dir.joinpath("scenes.json").read_text(encoding="utf-8").strip() == before.strip()
    assert ("compose",) in calls and read_json(p.dir / "revise.json")["kept"] is False


def test_watch_and_revise_leaves_a_good_video_alone(ref, monkeypatch):
    import vt.server.app as A

    assert A.watch_and_revise(None, {"risk": 10, "worst": []}, None, None) is False


def test_autopilot_is_a_setting(ref):
    from fastapi.testclient import TestClient
    from vt.server.app import app

    with TestClient(app) as c:
        assert c.put("/api/settings", json={"autopilot": True}).json()["autopilot"] is True
        assert c.get("/api/settings").json()["autopilot"] is True


def test_a_briefly_locked_file_is_deleted_after_a_retry(tmp_path, monkeypatch):
    # seen on the owner's machine (2026-10-23): WinError 32 on a just-rendered video stopped the revise step before it was recorded
    import pathlib

    import vt.server.app as A

    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    real, calls = pathlib.Path.unlink, []

    def flaky(self, missing_ok=False):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError(32, "in use")
        return real(self, missing_ok=missing_ok)

    monkeypatch.setattr(pathlib.Path, "unlink", flaky)
    monkeypatch.setattr(A.time, "sleep", lambda s: None)
    assert A._remove(f) and not f.exists() and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(pathlib.Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError(32, "in use")))
    assert A._remove(tmp_path / "w.mp4", tries=3) is False                  # gives up without raising


def test_frames_the_vision_model_flags_are_sent_to_the_director_even_when_the_score_is_good(ref, monkeypatch):
    import vt.server.app as A
    from vt import retention as RT
    from vt.ai import providers as AIP
    from vt.project import Project
    from vt.script import chat
    from vt.util import write_json

    p = Project("reference")
    write_json(p.dir / "video_script.json", {"scenes": []})
    sent = []
    monkeypatch.setattr(AIP, "ai_enabled", lambda: True)
    monkeypatch.setattr(A, "export", _fake_export([]))
    monkeypatch.setattr(A, "compose_all", lambda p: None)
    monkeypatch.setattr(RT, "scorecard", lambda *a, **k: {"risk": 11})
    monkeypatch.setattr(chat, "talk", lambda p, message, author="person", **k: sent.append(message) or {"ok": True, "reply": "ok"})
    p.exports_dir.mkdir(parents=True, exist_ok=True)
    (p.exports_dir / "first.mp4").write_bytes(b"x")
    qa = {"scenes": [{"id": "s2", "t": 4.0, "ok": False, "problems": ["cut_off"], "fix_hint": "the desk is cut", "source": "vlm"},
                     {"id": "s3", "t": 8.0, "ok": False, "problems": ["overlap"], "source": "vlm"}]}
    kept = A.watch_and_revise(p, {"risk": 10, "worst": []}, p.exports_dir / "first.mp4", lambda *a, **k: None, qa)
    assert kept and "scene s2 (at 4.0 s): something is cut off at the screen edge (the desk is cut)" in sent[0] and "scene s3" in sent[0]
