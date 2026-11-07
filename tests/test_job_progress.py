"""Displayed progress never goes backward because of a late stage heartbeat."""
from vt.server.jobs import JobManager
from test_job_queue import wait_for


def test_stage_progress_is_clamped_and_late_previous_stage_is_ignored():
    manager=JobManager(lambda event:None)
    seen=[]
    def work(progress):
        for stage,frac in [("asr",.7),("asr",.2),("asr",1.4),("plan",0),("asr",.9),("plan",.4)]:
            progress(stage,frac,"A new status")
            seen.append((manager.current.stage,manager.current.frac))
    job=manager.submit("pipeline",None,"Video",work);wait_for(job)
    assert seen==[("asr",.7),("asr",.7),("asr",1),("plan",0),("plan",0),("plan",.4)]
    assert all("140%" not in row["text"] and "20%" not in row["text"] for row in job.lines)
