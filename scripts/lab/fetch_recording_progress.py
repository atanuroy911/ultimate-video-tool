"""Fetch only this task's status/transcripts and render results from roy's home."""
from pathlib import Path
import argparse
import json
import os
import paramiko
from safe_get import safe_get
root='/home/roy/ultimate-video-tool-server/qa-recordings'
local=Path(__file__).resolve().parents[2]/'dist/recording-acceptance'
parser=argparse.ArgumentParser();parser.add_argument('--previews',action='store_true');parser.add_argument('--exports',action='store_true');args=parser.parse_args()
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=15)
s=c.open_sftp()
try:
    for name in ['transcribe-status.json','transcribe.log','render-status.json','render.log','render-smoke.json','edits.json']:
        try:
            safe_get(s,root+'/'+name,str(local/name))
            if name.endswith('status.json'):
                state=json.loads((local/name).read_text(encoding='utf-8'))
                if 'projects' in state:state['projects']={key:{'project':item['project'],'exported':bool(item.get('export'))} for key,item in state['projects'].items()}
                print(name,json.dumps(state))
        except FileNotFoundError:pass
    for number in [1,2]:
        for name in ['transcript.raw.json','transcript.txt']:
            try:safe_get(s,f'{root}/source-{number}/{name}',str(local/f'source-{number}'/name))
            except FileNotFoundError:pass
    try:safe_get(s,root+'/gpu-check/browser-render.log',str(local/'gpu-browser-render.log'))
    except FileNotFoundError:pass
    if (args.previews or args.exports) and (local/'edits.json').exists():
        for key,item in json.loads((local/'edits.json').read_text(encoding='utf-8')).items():
            if args.previews:
                target=local/'previews'/key;target.mkdir(parents=True,exist_ok=True)
                for remote in item.get('previews',[]):
                    if not remote.startswith(root+'/previews/'):raise RuntimeError('Unexpected preview path')
                    safe_get(s,remote,str(target/Path(remote).name))
            if args.exports and item.get('export'):
                remote=item['export'];expected='/home/roy/ultimate-video-tool-server/data/projects/'+item['project']+'/exports/'
                if not remote.startswith(expected):raise RuntimeError('Unexpected export path')
                target=local/'exports';target.mkdir(parents=True,exist_ok=True)
                filename=f"{item['source']}-{'subtitles' if item['mode']=='subtitles' else 'motion-graphics'}.mp4"
                try:safe_get(s,remote,str(target/filename))
                except FileNotFoundError:
                    print('Referenced export is missing:',key,remote)
                    continue
                try:safe_get(s,remote[:-4]+'.srt',str(target/filename.replace('.mp4','.srt')))
                except FileNotFoundError:pass
finally:s.close();c.close()
