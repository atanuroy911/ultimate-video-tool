"""Update only our server's recording support, refusing to interrupt active jobs."""
from pathlib import Path
import os
import shlex
import time
import paramiko
root='/home/roy/ultimate-video-tool-server'
local=Path(__file__).resolve().parents[2]/'server'
files=['vt/schema.py','vt/pipeline.py','vt/aroll.py','vt/screen_recording.py','vt/compose/composer.py','vt/server/app.py','vt/stages/asr.py','vt/render/hyperframes.py',
       'vt/render/browser_gpu.py','vt/render/chrome_gpu_launcher.py','renderer/runtime/vt.js','renderer/runtime/vt-media.js','renderer/runtime/vt.css']
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
s=c.open_sftp()
def run(command):
    _,out,err=c.exec_command(command);value=out.read().decode();error=err.read().decode()
    if out.channel.recv_exit_status():raise RuntimeError(error or value)
    return value
try:
    # The standalone QA worker is not an API job. Check it separately before
    # replacing runtime files that it could currently be reading.
    run("if pgrep -u roy -f '[p]ython edit.py' >/dev/null; then echo 'Recording QA worker is active; deployment deferred' >&2; exit 1; fi")
    check="import httpx; jobs=httpx.get('http://127.0.0.1:8790/api/jobs').json(); assert not any(j['status'] in ('queued','running') for j in jobs), 'A video job is active; deployment deferred'"
    run(root+'/venv/bin/python -c '+shlex.quote(check))
    existing=[]
    for name in files:
        try:s.stat(root+'/app/'+name);existing.append('app/'+name)
        except FileNotFoundError:pass
    run('cd '+root+' && tar -czf recording-before-'+str(int(time.time()))+'.tar.gz '+' '.join(shlex.quote(name) for name in existing))
    for name in files:s.put(str(local/name),root+'/app/'+name+'.recording-update')
    run(root+'/venv/bin/python -c '+shlex.quote(check))
    run('systemctl --user stop ultimate-video-tool.service')
    try:
        for name in files:s.posix_rename(root+'/app/'+name+'.recording-update',root+'/app/'+name)
        run(root+'/venv/bin/python -m compileall -q '+root+'/app/vt')
    finally:run('systemctl --user start ultimate-video-tool.service')
    print(run('systemctl --user is-active ultimate-video-tool.service'))
finally:s.close();c.close()
