"""Real native companion/remote-server check; credentials remain in memory."""
import os,json,subprocess,paramiko
from pathlib import Path
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False)
try:
 _,ready,errors=c.exec_command('curl -fsS --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8790/api/health')
 ready.read();assert ready.channel.recv_exit_status()==0,errors.read().decode()
 _,o,e=c.exec_command('curl -fsS -X POST http://127.0.0.1:8790/api/directors/token')
 auth=json.loads(o.read());device=auth['device']
 try:
  result=subprocess.run([r'C:\Program Files\nodejs\node.exe','client/desktop/test-live-companion.js'],input=json.dumps({'server':'http://192.168.123.47:8790','token':auth['token'],'verifyRun':True}),text=True,capture_output=True,timeout=180)
  Path('docs/evidence/client-remote-connection.log').write_text(result.stdout+result.stderr,encoding='utf-8')
  print(result.stdout,result.stderr);assert result.returncode==0
 finally:
  ident=device['id'] if isinstance(device,dict) else device
  _,o,e=c.exec_command('curl -fsS -X DELETE http://127.0.0.1:8790/api/server/clients/'+ident)
  o.read()
finally:c.close()
