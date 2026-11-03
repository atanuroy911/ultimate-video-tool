"""Snapshot the production-generated motion plan without changing that plan."""
from pathlib import Path
import os
import paramiko
import shlex
root='/home/roy/ultimate-video-tool-server'
local=Path(__file__).resolve().parents[2]/'dist/recording-acceptance/pipeline-motion-preview'
local.mkdir(exist_ok=True)
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
code="""import os,sys
from pathlib import Path
root=Path('/home/roy/ultimate-video-tool-server')
os.environ.update(VT_DATA=str(root/'data'),PATH=str(root/'node/bin')+':/usr/bin:/bin',TMPDIR=str(root/'tmp'),XDG_CACHE_HOME=str(root/'cache'))
sys.path.insert(0,str(root/'app'))
from vt.render.hyperframes import snapshot
for p in snapshot(root/'data/projects/qa-recording-1-screen-20261103/composition/16x9',root/'qa-recordings/previews/pipeline-motion',[62.24,107.37,201.6,217.15],gpu=False):print(p)
"""
try:
 _,out,err=c.exec_command(root+'/venv/bin/python -c '+shlex.quote(code));value=out.read().decode();error=err.read().decode()
 if out.channel.recv_exit_status():raise RuntimeError(error or value)
 s=c.open_sftp()
 for name in s.listdir(root+'/qa-recordings/previews/pipeline-motion'):
  if name.startswith('frame-') and name.endswith('.png'):s.get(root+'/qa-recordings/previews/pipeline-motion/'+name,str(local/name))
 print(value)
finally:c.close()
