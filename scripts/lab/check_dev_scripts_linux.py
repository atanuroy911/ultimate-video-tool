"""Exercise the common developer installer in a disposable home-folder Linux fixture."""
import os
from pathlib import Path
import paramiko

local=Path(__file__).resolve().parents[2]
root='/home/roy/ultimate-video-tool-server'
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
s=c.open_sftp()
try:
    folder=root+'/qa-dev-scripts'
    _,out,err=c.exec_command('mkdir -p '+folder)
    assert out.channel.recv_exit_status()==0,err.read().decode()
    for name in ['dev-install.sh','dev-install.mjs','test-dev-install.mjs','setup.sh','start.sh']:
        s.put(str(local/'scripts'/name),folder+'/'+name)
    command=f'export PATH="{root}/node/bin:/usr/bin:/bin" TMPDIR="{root}/tmp"; bash -n "{folder}/dev-install.sh" && bash -n "{folder}/setup.sh" && bash -n "{folder}/start.sh" && node "{folder}/test-dev-install.mjs"'
    _,out,err=c.exec_command(command)
    text=out.read().decode()+err.read().decode();print(text)
    assert out.channel.recv_exit_status()==0,text
finally:s.close();c.close()
