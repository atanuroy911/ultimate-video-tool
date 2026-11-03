"""Copy the owner's recordings to their GPU server, leaving originals untouched."""
from pathlib import Path
import os
import paramiko

local=Path(__file__).resolve().parents[2]
root='/home/roy/ultimate-video-tool-server/qa-recordings'
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
s=c.open_sftp()
try:
    _,out,err=c.exec_command('mkdir -p '+root+'/source-1 '+root+'/source-2')
    assert out.channel.recv_exit_status()==0,err.read().decode()
    for number,source in enumerate(sorted(local.glob('*.mp4')),1):
        if number>2:raise RuntimeError('Expected exactly the two inspected recordings.')
        destination=f'{root}/source-{number}'
        for origin,name in [(source,'original.mp4'),(local/f'dist/recording-acceptance/source-{number}/speech.wav','speech.wav')]:
            try:exists=s.stat(destination+'/'+name).st_size==origin.stat().st_size
            except FileNotFoundError:exists=False
            if not exists:s.put(str(origin),destination+'/'+name)
        print('Uploaded source',number,flush=True)
    s.put(str(local/'scripts/lab/recording_transcribe_worker.py'),root+'/transcribe.py')
    launcher='''#!/bin/bash
set -euo pipefail
cd /home/roy/ultimate-video-tool-server/qa-recordings
/home/roy/.local/bin/uv pip install --python ../venv/bin/python --target cuda-runtime 'nvidia-cublas-cu12>=12,<13' 'nvidia-cudnn-cu12>=9,<10'
export LD_LIBRARY_PATH="$PWD/cuda-runtime/nvidia/cublas/lib:$PWD/cuda-runtime/nvidia/cudnn/lib:${LD_LIBRARY_PATH:-}"
exec ../venv/bin/python transcribe.py
'''
    with s.file(root+'/run-transcription.sh','w') as stream:stream.write(launcher)
    command=f'cd {root} && (nohup bash run-transcription.sh > transcribe.log 2>&1 < /dev/null & echo $!)'
    _,out,err=c.exec_command(command)
    print('Transcription worker started:',out.read().decode().strip());print(err.read().decode())
finally:s.close();c.close()
