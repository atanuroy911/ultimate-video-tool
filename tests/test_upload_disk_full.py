"""A full disk is an actionable upload failure and its actual offset survives."""
import asyncio
import errno
import pytest
from fastapi import HTTPException
from vt.server import uploads as U


class Stream:
    def __init__(self,full): self.full=full
    async def stream(self):
        yield b"12"
        if self.full: raise OSError(errno.ENOSPC,"No space left on device")
        yield b"34"


def test_full_disk_job_has_a_plain_recoverable_message():
    from vt.server.jobs import JobManager
    from test_job_queue import wait_for
    def fail(progress): raise OSError(errno.ENOSPC,"No space left: /private/server/path")
    job=JobManager(lambda event:None).submit("pipeline",None,"Make video",fail)
    wait_for(job)
    assert job.status=="error" and "Free some space" in job.error
    assert "/private" not in job.error


def test_atomic_stage_save_keeps_previous_document_on_full_disk(tmp_path,monkeypatch):
    from pathlib import Path
    from vt.util import write_json,read_json
    target=tmp_path/"stage.json"
    write_json(target,{"finished":True})
    original=Path.write_text
    def no_space(self,text,*args,**kwargs):
        if self.suffix==".tmp": raise OSError(errno.ENOSPC,"No space")
        return original(self,text,*args,**kwargs)
    monkeypatch.setattr(Path,"write_text",no_space)
    with pytest.raises(OSError):write_json(target,{"finished":False})
    assert read_json(target)=={"finished":True}


@pytest.mark.parametrize("whole",[False,True])
def test_full_disk_reports_space_needed_and_upload_can_resume(tmp_path,monkeypatch,whole):
    monkeypatch.setattr(U,"_dir",lambda:tmp_path)
    upload=U.start(U.NewUpload(name="recording.wav",size=4))
    uid=upload["id"]
    with pytest.raises(HTTPException) as error:
        asyncio.run(U.whole(uid,Stream(True)) if whole else U.chunk(uid,0,Stream(True)))
    assert error.value.status_code==507
    assert "space" in str(error.value.detail).lower()
    assert U.status(uid)["offset"]==2
    class Rest:
        async def stream(self): yield b"34"
    assert asyncio.run(U.chunk(uid,2,Rest()))["done"]
    assert U.path_of(uid)[0].read_bytes()==b"1234"
