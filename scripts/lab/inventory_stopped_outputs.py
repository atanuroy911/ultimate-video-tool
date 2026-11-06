import os,json,paramiko
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy());c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
s=c.open_sftp();r='/home/roy/ultimate-video-tool-server'
for path in [r,r+'/data',r+'/data/projects',r+'/qa-recordings/rejected']:
 try: print(path,s.listdir(path)[:25])
 except OSError as e: print(path,type(e).__name__,str(e))
for item in json.loads(open('dist/recording-acceptance/edits.json',encoding='utf-8').read()).values():
 path=r+'/data/projects/'+item['project']+'/exports'
 try: print(path,s.listdir(path))
 except OSError as e: print(path,type(e).__name__,str(e))
s.close();c.close()
