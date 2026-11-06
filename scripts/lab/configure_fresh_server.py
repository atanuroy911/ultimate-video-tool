"""Finish our isolated home-folder deployment; never change existing engine installs."""
import os
from pathlib import Path
import paramiko

local=Path(__file__).resolve().parents[2]
root='/home/roy/ultimate-video-tool-server'
c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
s=c.open_sftp()
try:
    for name in ['vt/tts.py','vt/project.py','vt/server/app.py','vt/direction/editor.py','vt/modules/defs/reel.py']:
        s.put(str(local/name),root+'/app/'+name)
    for p in (local/'studio/dist').rglob('*'):
        if not p.is_file():continue
        dest=root+'/app/studio/dist/'+p.relative_to(local/'studio/dist').as_posix()
        s.put(str(p),dest)
    import json
    settings={'llm_mode':'auto','ai_provider':'ollama','ollama_url':'http://127.0.0.1:11434','ollama_model':'gemma4:latest',
              'comfy_url':'http://127.0.0.1:8188','autopilot':False,'default_aspect':'9:16','plan_review':'auto'}
    try:
        if s.stat(root+'/data/settings.json').st_size:
            raise RuntimeError('Settings already populated; refusing to replace them.')
    except FileNotFoundError:
        pass
    with s.file(root+'/data/settings.json','w') as f:f.write(json.dumps(settings,indent=2))
    runner='''#!/bin/bash
set -euo pipefail
ROOT=/home/roy/ultimate-video-tool-server
export VT_DATA="$ROOT/data" PATH="$ROOT/node/bin:/usr/bin:/bin" TMPDIR="$ROOT/tmp" XDG_CACHE_HOME="$ROOT/cache" HYPERFRAMES_NO_TELEMETRY=1 PYTHONIOENCODING=utf-8
cd "$ROOT/app"
exec "$ROOT/venv/bin/python" -m vt.cli server --host 0.0.0.0 --port 8790 --name "Ultimate Video Tool Server" --comfy existing --comfy-url http://127.0.0.1:8188 --ollama existing --ollama-url http://127.0.0.1:11434 --voicestudio off
'''
    with s.file(root+'/run-server.sh','w') as f:f.write(runner)
    s.chmod(root+'/run-server.sh',0o700)
    unit='''[Unit]
Description=Ultimate Video Tool Server (home install)
After=network-online.target
[Service]
ExecStart=/home/roy/ultimate-video-tool-server/run-server.sh
WorkingDirectory=/home/roy/ultimate-video-tool-server/app
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/roy/ultimate-video-tool-server/server.log
StandardError=append:/home/roy/ultimate-video-tool-server/server.log
[Install]
WantedBy=default.target
'''
    # Only user configuration beneath /home/roy; no sudo or system services.
    _,o,e=c.exec_command('mkdir -p /home/roy/.config/systemd/user')
    assert o.channel.recv_exit_status()==0,e.read().decode()
    with s.file('/home/roy/.config/systemd/user/ultimate-video-tool.service','wx') as f:f.write(unit)
    _,o,e=c.exec_command('systemctl --user daemon-reload && systemctl --user enable --now ultimate-video-tool.service && systemctl --user is-active ultimate-video-tool.service')
    print(o.read().decode(),e.read().decode())
    assert o.channel.recv_exit_status()==0
finally:s.close();c.close()
