"""Update only the isolated Video Tool install, with a code/UI rollback archive."""
import os,tarfile,json
from pathlib import Path
import paramiko
local=Path(__file__).resolve().parents[2];root='/home/roy/ultimate-video-tool-server'
names=['vt/directors.py','vt/pipeline.py','vt/llm.py','vt/server/app.py','vt/server/setup_routes.py','vt/server/engines_routes.py',
       'vt/engines/setup.py','vt/engines/installers.py','vt/engines/prepare.py','vt/server/management.html','vt/server/management.js','vt/server/engine-management.html','vt/server/engine-management.js']
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False)
s=c.open_sftp()
try:
    _,o,e=c.exec_command('cd '+root+' && tar -czf architecture-before.tar.gz app/vt')
    assert o.channel.recv_exit_status()==0,e.read().decode()
    for name in names:s.put(str(local/'server'/name),root+'/app/'+name)
    try:
        s.stat(root+'/app/studio')
    except FileNotFoundError:
        pass
    else:
        import time
        s.rename(root+'/app/studio','/home/roy/ultimate-video-tool-legacy-client-ui-'+str(int(time.time())))
    _,o,e=c.exec_command('cd '+root+' && ./venv/bin/python -m compileall -q app/vt && systemctl --user restart ultimate-video-tool.service && systemctl --user is-active ultimate-video-tool.service')
    print(o.read().decode(),e.read().decode());assert o.channel.recv_exit_status()==0
finally:s.close();c.close()
