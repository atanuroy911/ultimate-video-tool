"""Launch only this task's editable-project preparation or four-video render."""
from pathlib import Path
import argparse
import os
import paramiko
parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');parser.add_argument('--refresh-previews',action='store_true');parser.add_argument('--smoke',action='store_true');parser.add_argument('--full-pipeline',action='store_true');parser.add_argument('--smoke-only',action='store_true');parser.add_argument('--gpu-smoke',action='store_true');args=parser.parse_args()
local=Path(__file__).resolve().parents[2]
root='/home/roy/ultimate-video-tool-server/qa-recordings'
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
s=c.open_sftp()
try:
    script='pipeline.py' if args.full_pipeline else 'edit.py'
    s.put(str(local/'scripts/lab'/('recording_pipeline_worker.py' if args.full_pipeline else 'recording_edit_worker.py')),root+'/'+script)
    runtime=f'{root}/cuda-runtime/nvidia/cublas/lib:{root}/cuda-runtime/nvidia/cudnn/lib'
    command=f'cd {root} && (nohup env LD_LIBRARY_PATH={runtime} flock -n edits.lock ../venv/bin/python '+script
    if args.full_pipeline and args.smoke_only:command+=' --smoke-only'
    if args.full_pipeline and args.gpu_smoke:command+=' --gpu-smoke'
    if not args.full_pipeline:command+=(' --render' if args.render else '')+(' --refresh-previews' if args.refresh_previews else '')+(' --smoke' if args.smoke else '')
    command+=' > render.log 2>&1 < /dev/null & echo $!)'
    _,out,err=c.exec_command(command)
    print('Recording edit worker:',out.read().decode().strip());print(err.read().decode())
finally:s.close();c.close()
