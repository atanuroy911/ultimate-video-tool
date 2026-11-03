"""Check RTX 3060 encoding without changing engines or unrelated GPU workloads."""
import os
import paramiko
import shlex
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
code="""from pathlib import Path
import os,subprocess,json
root=Path('/home/roy/ultimate-video-tool-server/qa-recordings/gpu-check');root.mkdir(exist_ok=True)
raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,pci.bus_id,index,utilization.gpu,memory.used','--format=csv,noheader'],text=True)
print(raw,flush=True)
gpu=next(line.split(',')[1].strip() for line in raw.splitlines() if 'RTX 3060' in line)
env={**os.environ,'CUDA_VISIBLE_DEVICES':gpu,'CUDA_DEVICE_ORDER':'PCI_BUS_ID'}
args=['ffmpeg','-y','-hide_banner','-loglevel','verbose','-f','lavfi','-i','testsrc2=size=1920x1080:rate=30','-t','2','-an','-c:v','h264_nvenc','-gpu','0',str(root/'nvenc-test.mp4')]
r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=30)
(root/'nvenc-test.log').write_text(r.stderr)
print('NVENC test exit:',r.returncode,flush=True)
print(r.stderr[-6500:],flush=True)
if r.returncode:raise SystemExit(r.returncode)
"""
try:
 _,out,err=c.exec_command('/home/roy/ultimate-video-tool-server/venv/bin/python -c '+shlex.quote(code))
 print(out.read().decode());error=err.read().decode()
 if error:print(error)
 if out.channel.recv_exit_status():raise RuntimeError('GPU encoder verification failed')
finally:c.close()
