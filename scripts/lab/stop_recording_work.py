"""Stop only this task's remote QA workers and their process descendants."""
import os
import paramiko
import shlex
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
code="""from pathlib import Path
import json,os,signal,subprocess,time
root=Path('/home/roy/ultimate-video-tool-server/qa-recordings').resolve()
rows={int(a):int(b) for a,b in (line.split() for line in subprocess.check_output(['ps','-u','roy','-o','pid=,ppid='],text=True).splitlines())}
targets=set()
for pid in rows:
 try:
  command=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\\0',b' ').decode()
  if Path(f'/proc/{pid}/cwd').resolve()==root and any(name in command for name in ('python pipeline.py','python edit.py','python transcribe.py')):
   targets.add(pid)
 except (OSError,UnicodeError):pass
while True:
 children={pid for pid,parent in rows.items() if parent in targets}
 if children<=targets:break
 targets|=children
identities={}
for pid in targets:
 try:identities[pid]=Path(f'/proc/{pid}/stat').read_text().split()[21]
 except OSError:pass
for pid in sorted(targets,reverse=True):
 try:os.kill(pid,signal.SIGTERM)
 except ProcessLookupError:pass
time.sleep(2)
for pid,start in identities.items():
 try:
  if Path(f'/proc/{pid}/stat').read_text().split()[21]==start:os.kill(pid,signal.SIGKILL)
 except (OSError,ProcessLookupError):pass
status=root/'render-status.json'
previous=json.loads(status.read_text()) if status.exists() else {}
status.write_text(json.dumps({'stage':'stopped-by-owner','previous':previous,'stopped_processes':sorted(targets)},indent=2))
print('Stopped QA process tree:',sorted(targets))
print('Completed exports remain in edits.json. No engine/service was stopped.')
"""
try:
 _,out,err=c.exec_command('/home/roy/ultimate-video-tool-server/venv/bin/python -c '+shlex.quote(code));print(out.read().decode());error=err.read().decode()
 if out.channel.recv_exit_status():raise RuntimeError(error)
finally:c.close()
