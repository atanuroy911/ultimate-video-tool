"""Deploy our built full-server archive into a new, isolated folder in roy's home."""
import os
from pathlib import Path
import paramiko

root='/home/roy/ultimate-video-tool-server'
archive=Path(__file__).resolve().parents[2]/'dist/video-tool-engine-1.0.0.tar.gz'
client=paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.123.47',username='roy',password=os.environ['GPU_PASS'],look_for_keys=False,allow_agent=False,timeout=20)
sftp=client.open_sftp()
try:
    try:
        sftp.lstat(root)
    except FileNotFoundError:
        sftp.mkdir(root,mode=0o700)
    else:
        raise RuntimeError('Fresh install destination already exists; refusing to replace it.')
    sftp.put(str(archive),root+'/install.tar.gz')
    install=r'''#!/bin/bash
set -euo pipefail
ROOT=/home/roy/ultimate-video-tool-server
cd "$ROOT"
mkdir -p app data cache tmp python
export TMPDIR="$ROOT/tmp" UV_CACHE_DIR="$ROOT/cache/uv" UV_PYTHON_INSTALL_DIR="$ROOT/python" UV_PROJECT_ENVIRONMENT="$ROOT/venv"
tar -xzf install.tar.gz -C app --strip-components=1
cd app
/home/roy/.local/bin/uv sync --frozen --no-dev --extra cpu --python 3.11
cd renderer
npm ci --no-audit --no-fund --cache "$ROOT/cache/npm"
cd "$ROOT"
printf 'INSTALL_OK\n'
'''
    with sftp.file(root+'/install.sh','w') as f:
        f.write(install)
    sftp.chmod(root+'/install.sh',0o700)
    _,stdout,stderr=client.exec_command(f'nohup bash {root}/install.sh > {root}/install.log 2>&1 < /dev/null & echo $!')
    print('Fresh install started, PID',stdout.read().decode().strip())
    print(stderr.read().decode())
finally:
    sftp.close()
    client.close()
