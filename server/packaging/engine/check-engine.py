"""Prove this install starts, then always stop only the process we launched."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def check(app: Path, data: Path, port: int, timeout: float = 60) -> dict:
    if not 1 <= port <= 65535:
        raise ValueError('Choose a port between 1 and 65535.')
    # An existing engine must never make a broken new install appear healthy.
    with socket.socket() as probe:
        if os.name == 'nt':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError as error:
            raise RuntimeError(f'Port {port} is already in use. Choose another --port for this installation check.') from error
    data.mkdir(parents=True, exist_ok=True)
    env={**os.environ, 'VT_DATA':str(data), 'PYTHONPATH':str(app), 'PYTHONUNBUFFERED':'1'}
    process=None
    with (data.parent/'check.log').open('w',encoding='utf-8') as log:
        try:
            process=subprocess.Popen([sys.executable,'-m','vt.cli','engine','run','--port',str(port),'--engines','','--no-start'],
                cwd=app,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'The installed engine exited ({process.returncode}); see check.log.')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/.well-known/vt-engine',timeout=1) as response:
                        result=json.load(response)
                    if not isinstance(result,dict) or not result.get('engine_server'):
                        raise RuntimeError('The answer is not an engine document.')
                    if process.poll() is not None:
                        raise RuntimeError('The installed engine stopped during its readiness check.')
                    (data.parent/'check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                    return result
                except (urllib.error.URLError,TimeoutError):
                    time.sleep(.2)
            raise RuntimeError('The installed engine did not answer within the startup limit; see check.log.')
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    try:
        result=check(args.app.resolve(),args.data.resolve(),args.port)
    except (OSError,RuntimeError,ValueError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
    print(json.dumps(result));print('OK: the installed engine starts, answers, and stops cleanly.')
