"""Cancellation is control flow, never a model failure that starts a fallback."""
import pytest
from vt.pipeline import Pipeline, ORDER
from vt.server.jobs import Cancelled, JobManager
from vt.util import write_json


@pytest.mark.parametrize("stage",ORDER)
def test_cancel_inside_each_stage_preserves_checkpoints_and_can_continue(ref,monkeypatch,stage):
    from vt import gpu
    from vt.modules.executor import Executor
    write_json(ref.script_path,{"text":"A test script"})
    monkeypatch.setattr(gpu,"prepare",lambda:None)
    monkeypatch.setattr(Pipeline,"_director_provider",lambda *args:None)
    monkeypatch.setattr(Pipeline,"director",lambda self:"rules")
    cancelled=False
    fallback=[]
    finished=[]
    def progress(name,frac,msg):
        if cancelled:raise Cancelled()
    def call(self,module,inputs,**kwargs):
        nonlocal cancelled
        name=module.split(".")[-1]
        if ref.stage_done(name,"test-input"):return
        if name==stage and not finished:
            cancelled=True
            try:self.ws.pipeline._say(name,.5,"Working")
            except Exception:fallback.append(name)
        ref.mark_stage(name,"test-input")
    monkeypatch.setattr(Executor,"call",call)
    with pytest.raises(Cancelled):Pipeline(ref,progress).run()
    assert not fallback,"Cancel must not start a model/rule fallback"
    assert ref.meta().status=="cancelled"
    assert not ref.stage_done(stage,"test-input")
    previous={k:v for k,v in ref.meta().stages.items() if v.get("hash")=="test-input"}
    assert list(previous)==ORDER[:ORDER.index(stage)]
    cancelled=False;finished.append(True)
    Pipeline(ref,progress).run()
    assert ref.meta().status=="planned"
    assert all(ref.stage_done(name,"test-input") for name in ORDER)
    assert all(ref.meta().stages[k]==v for k,v in previous.items())


def test_cancellation_at_return_does_not_report_success():
    from test_job_queue import wait_for
    manager=JobManager(lambda event:None)
    def work(progress):
        manager.current.cancel.set()
        return "should not be reported as a finished video"
    job=manager.submit("pipeline",None,"Video",work)
    wait_for(job)
    assert job.status=="cancelled"


def test_module_records_cancellation_instead_of_an_engine_failure(ref,monkeypatch):
    from vt.modules.executor import Executor
    from vt.util import read_json
    def stop(self,force=False):raise Cancelled()
    monkeypatch.setattr(Pipeline,"stage_context",stop)
    result=Executor(ref.dir,pipeline=Pipeline(ref)).call("pipeline.context",{"force":True},skip_prerequisites=True)
    assert result.status=="cancelled" and not result.ok
    assert "pipeline.context" not in str(read_json(ref.dir/".module_cache.json",{}))
