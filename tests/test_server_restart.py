"""Restart has to identify this server, reject busy work and fence new jobs."""
import os
import threading
from types import SimpleNamespace
import pytest
from fastapi import BackgroundTasks, HTTPException
from vt.server import restart as R
from vt.server.jobs import JobManager,ServerRestarting


def test_only_own_systemd_user_service_is_offered(monkeypatch):
    monkeypatch.setattr(R.sys,"platform","linux")
    monkeypatch.setattr(R.os,"getuid",lambda:1000,raising=False)
    monkeypatch.setattr(R,"_cgroup",lambda:"0::/user.slice/user-1000.slice/user@1000.service/app.slice/video-tool.service")
    calls=[]
    monkeypatch.setattr(R.subprocess,"run",lambda args,**kwargs:calls.append(args) or SimpleNamespace(returncode=0,stdout=str(os.getpid())))
    assert R.describe()["unit"]=="video-tool.service"
    assert calls[0][-1]=="video-tool.service"
    monkeypatch.setattr(R.subprocess,"run",lambda *a,**k:SimpleNamespace(returncode=0,stdout="99999999"))
    assert not R.describe()["available"]


@pytest.mark.parametrize("cgroup",["0::/system.slice/ollama.service","0::/user.slice/user@1000.service/app.slice/bad;command.service","0::/user.slice/user@1000.service/session.scope"])
def test_unverified_supervisor_never_offers_restart(monkeypatch,cgroup):
    monkeypatch.setattr(R.sys,"platform","linux")
    monkeypatch.setattr(R.os,"getuid",lambda:1000,raising=False)
    monkeypatch.setattr(R,"_cgroup",lambda:cgroup)
    monkeypatch.setattr(R.subprocess,"run",lambda *a,**k:pytest.fail("must not run a command"))
    assert not R.describe()["available"]


def test_restart_is_refused_while_work_is_queued_or_running(monkeypatch):
    monkeypatch.setattr(R,"describe",lambda:{"available":True,"unit":"video-tool.service"})
    manager=JobManager(lambda e:None);gate=threading.Event()
    manager.submit("pipeline",None,"Video",lambda cb:gate.wait(5))
    try:
        with pytest.raises(HTTPException) as error:R.request(manager,BackgroundTasks())
        assert error.value.status_code==409
    finally:gate.set()


def test_scheduled_restart_fences_new_work_and_failed_command_releases_it(monkeypatch):
    monkeypatch.setattr(R,"describe",lambda:{"available":True,"unit":"video-tool.service"})
    manager=JobManager(lambda e:None);background=BackgroundTasks()
    assert R.request(manager,background)["restarting"]
    assert len(background.tasks)==1
    with pytest.raises(ServerRestarting):manager.submit("pipeline",None,"Video",lambda cb:None)
    monkeypatch.setattr(R.subprocess,"run",lambda *a,**k:SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError):R.execute(manager,"video-tool.service")
    assert manager.submit("pipeline",None,"Video",lambda cb:None)
