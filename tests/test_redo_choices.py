"""Direct again changes only this video's director/style, including story/reel/auto."""
import pytest
from vt.server import app as A
from vt.server.jobs import Job, JobManager
from vt.script import service


@pytest.mark.parametrize("kind",["auto","story","reel","stick","emoji","cartoon","mixed","infographic","explainer"])
def test_direct_again_uses_project_choices(ref,monkeypatch,kind):
    calls=[]
    monkeypatch.setattr(A,"jobs",JobManager(lambda event:None))
    monkeypatch.setattr(A,"start_pipeline",lambda p,start,force,rerender: calls.append((start,force,rerender)) or Job("new","pipeline",p.id,"Direct"))
    response=A.run_project(ref.id,A.RunBody(from_stage="plan",force=True,director="claude@laptop",video_kind=kind))
    assert response["id"]=="new"
    assert ref.meta().options.director=="claude@laptop"
    assert ref.meta().options.look==({"story":"story","reel":"reel"}.get(kind,"classic"))
    assert service.script_kind(ref)==(kind if kind not in ("auto","story","reel") else "explainer")
    assert calls==[("plan",True,False)]


def test_unknown_redo_style_is_rejected_before_work(ref,monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(A,"jobs",JobManager(lambda event:None))
    with pytest.raises(HTTPException) as err:
        A.run_project(ref.id,A.RunBody(video_kind="not-a-style"))
    assert err.value.status_code==400
