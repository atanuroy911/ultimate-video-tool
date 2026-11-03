"""Read only the home-folder speech models and our own server launch settings."""
import os
import shlex
import paramiko
code='''
from pathlib import Path
import json, shutil
home=Path('/home/roy');root=home/'ultimate-video-tool-server'
models=[]
for folder in [home/'.cache/huggingface/hub',root/'data/models',root/'cache/huggingface/hub']:
    if folder.exists():
        for pattern in ['*/model.bin','models--*whisper*/snapshots/*/model.bin']:
            models += [str(p.parent) for p in folder.glob(pattern)]
launch=[]
libraries=[]
patterns=['*/.venv/lib/python3.*/site-packages/nvidia/*/lib','*/venv/lib/python3.*/site-packages/nvidia/*/lib',
          '.cache/uv/archive-v0/*/nvidia/*/lib','miniconda3/envs/*/lib/python3.*/site-packages/nvidia/*/lib']
for pattern in patterns:
    libraries += [str(p) for p in home.glob(pattern) if (p/'libcublas.so.12').exists() or (p/'libcudnn.so.9').exists()]
for f in [root/'run-server.sh',home/'.config/systemd/user/ultimate-video-tool.service']:
    if f.exists(): launch += [line for line in f.read_text().splitlines() if 'CUDA_VISIBLE_DEVICES' in line]
print(json.dumps({'models':models,'cuda_libraries':libraries,'gpu_selection':launch,'free_gb':round(shutil.disk_usage(root).free/1e9,1)}))
'''
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
try:
    _,out,err=c.exec_command('/home/roy/ultimate-video-tool-server/venv/bin/python -c '+shlex.quote(code))
    print(out.read().decode());assert out.channel.recv_exit_status()==0,err.read().decode()
finally:c.close()
