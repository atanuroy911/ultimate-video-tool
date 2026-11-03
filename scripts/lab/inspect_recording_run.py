"""Read only this task's worker and a small allowlist of provider settings."""
import os
import paramiko
import shlex
import sys
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
root='/home/roy/ultimate-video-tool-server'
script='''import json,pathlib,httpx
p=pathlib.Path('/home/roy/ultimate-video-tool-server/data/settings.json')
s=json.loads(p.read_text())
print('AI settings:',json.dumps({k:s.get(k) for k in ['ai_provider','llm_mode','ollama_model','comfy_url','ollama_url']}))
for route in ['tags','ps']:
 try:
  r=httpx.get((s.get('ollama_url') or 'http://127.0.0.1:11434').rstrip('/')+'/api/'+route,timeout=3)
  print('Ollama '+route,json.dumps([{'name':m.get('name'),'size_vram':m.get('size_vram')} for m in r.json().get('models',[])]))
 except Exception as e:print('Ollama '+route,type(e).__name__)
for p in pathlib.Path('/home/roy/ultimate-video-tool-server/data/projects').glob('qa-recording-*/context.json'):
 print(p.parent.name,'context exists',p.stat().st_size)
comp=pathlib.Path('/home/roy/ultimate-video-tool-server/data/projects/qa-recording-1-subtitles-20261103/composition/16x9')
d=json.loads((comp/'data.json').read_text())
print('Render data:',json.dumps({'format':d['format'],'duration':d['duration'],'media':d['media'],'scenes':[{'start':x['start'],'end':x['end'],'backdrop':x.get('backdrop')} for x in d['scenes']]}))
print('Video IDs deployed:',"node.id = 'vt-video-'" in (comp/'runtime/vt-media.js').read_text())
print('HyperFrames:',json.loads(pathlib.Path('/home/roy/ultimate-video-tool-server/app/renderer/node_modules/hyperframes/package.json').read_text())['version'])
'''
try:
 if '--stop' in sys.argv:
  stop="""import os,pathlib,signal,subprocess
root=pathlib.Path('/home/roy/ultimate-video-tool-server/qa-recordings').resolve()
pids=subprocess.run(['pgrep','-u','roy','-f','[p]ython pipeline.py'],capture_output=True,text=True).stdout.split()
for value in pids:
 pid=int(value)
 if pathlib.Path(f'/proc/{pid}/comm').read_text().strip()=='python' and pathlib.Path(f'/proc/{pid}/cwd').resolve()==root:
  os.kill(pid,signal.SIGTERM);print('Stopped only QA pipeline worker',pid)
"""
  _,out,err=c.exec_command(root+'/venv/bin/python -c '+shlex.quote(stop));print(out.read().decode());print(err.read().decode())
 for command in [root+'/venv/bin/python -c '+shlex.quote(script),"for p in $(pgrep -u roy -f '[p]ython pipeline.py'); do ps -o pid,ppid,etime,pcpu,stat,wchan,comm -p $p; done"]:
  _,out,err=c.exec_command(command);print(out.read().decode());print(err.read().decode())
finally:c.close()
