"""Readiness for a disposable split-product workflow; no engine changes."""
import argparse
import json
import os
import shlex
import paramiko

parser = argparse.ArgumentParser()
parser.add_argument('--project', default='')
args = parser.parse_args()
code = '''
import json, httpx
base='http://127.0.0.1:8790'
out={}
with httpx.Client(timeout=20) as c:
    for name,url in [('health',base+'/api/health'),('comfy_queue','http://127.0.0.1:8188/queue'),('devices','http://127.0.0.1:8188/system_stats'),('voices',base+'/api/voices')]:
        r=c.get(url);r.raise_for_status();data=r.json()
        if name=='voices': data=[{'id':v['id'],'label':v['label'],'available':v.get('available'),'voices':len(v.get('voices',[]))} for v in data]
        if name=='comfy_queue': data={key:[item[1] for item in data.get(key,[])] for key in ['queue_running','queue_pending']}
        if name=='devices': data=data.get('devices',[])
        out[name]=data
    if PROJECT:
        r=c.get(base+'/api/jobs');r.raise_for_status();out['jobs']=[j for j in r.json() if j.get('project')==PROJECT]
print(json.dumps(out))
'''.replace('PROJECT',repr(args.project))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.123.47', username='roy', password=os.environ['GPU_PASS'], look_for_keys=False, allow_agent=False, timeout=15)
try:
    root='/home/roy/ultimate-video-tool-server'
    _, out, err = ssh.exec_command('cd '+root+' && ./venv/bin/python -c '+shlex.quote(code))
    result=out.read().decode();error=err.read().decode()
    if out.channel.recv_exit_status(): raise RuntimeError(error)
    print(result)
finally:
    ssh.close()
