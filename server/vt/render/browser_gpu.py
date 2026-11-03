"""Bind CUDA encoding and Linux browser drawing to the same usable GPU."""
from __future__ import annotations
import os
from pathlib import Path
import shlex
import subprocess
import sys
from ..util import CREATE_NO_WINDOW,find_tool


def nvidia_render_device():
    """Probe real encoding, not just an encoder name compiled into FFmpeg."""
    try:
        rows=subprocess.check_output(['nvidia-smi','--query-gpu=index,name,uuid,memory.free','--format=csv,noheader,nounits'],
            text=True,timeout=8,creationflags=CREATE_NO_WINDOW)
        devices=[(a.strip(),b.strip(),c.strip(),int(d.strip())) for a,b,c,d in (line.split(',') for line in rows.splitlines())]
        selected=os.environ.get('CUDA_VISIBLE_DEVICES','')
        if selected:
            devices=[device for device in devices if device[0] in selected.split(',') or device[2] in selected.split(',')]
        devices.sort(key=lambda device:device[3],reverse=True)
        for _,name,uuid,_ in devices:
            env={**os.environ,'CUDA_DEVICE_ORDER':'PCI_BUS_ID','CUDA_VISIBLE_DEVICES':uuid}
            result=subprocess.run([find_tool('ffmpeg'),'-v','error','-f','lavfi','-i','color=s=640x360:r=30',
                '-frames:v','1','-an','-c:v','h264_nvenc','-gpu','0','-f','null','-'],env=env,
                capture_output=True,timeout=12,creationflags=CREATE_NO_WINDOW)
            if result.returncode==0:return {'name':name,'uuid':uuid}
            import logging
            logging.getLogger(__name__).warning('GPU encoder probe failed for %s: %s',name,result.stderr.decode(errors='replace')[-1000:] if isinstance(result.stderr,bytes) else str(result.stderr)[-1000:])
    except (OSError,ValueError,subprocess.SubprocessError,RuntimeError):pass
    # HyperFrames still probes AMD/Intel/Apple hardware when NVIDIA is absent.
    return None


def browser_environment(work:Path,device):
    if not device:return {}
    env={'CUDA_DEVICE_ORDER':'PCI_BUS_ID','CUDA_VISIBLE_DEVICES':device['uuid'],'ANGLE_PREFERRED_DEVICE':device['name']}
    if sys.platform!='linux':return env
    candidates=[Path(value) for key in ('HYPERFRAMES_BROWSER_PATH','PRODUCER_HEADLESS_SHELL_PATH') if (value:=os.environ.get(key))]
    from ..util import tool_dirs
    for folder in tool_dirs():candidates.extend((folder/'chrome').glob('**/chrome-headless-shell'))
    candidates.extend((Path.home()/'.cache/hyperframes/chrome/chrome-headless-shell').glob('*/chrome-headless-shell-linux64/chrome-headless-shell'))
    real=next((path.resolve() for path in candidates if path.is_file() and path.name!='vt-gpu-chrome'),None)
    if real is None:raise RuntimeError('The renderer browser is missing. Repair the server installation before GPU rendering.')
    work.mkdir(parents=True,exist_ok=True)
    launcher=work/'chrome-headless-shell'
    script=Path(__file__).with_name('chrome_gpu_launcher.py')
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(script))+' "$@"\n',encoding='utf-8')
    launcher.chmod(0o700)
    env.update(VT_RENDER_CHROME_REAL=str(real),HYPERFRAMES_BROWSER_PATH=str(launcher),PRODUCER_HEADLESS_SHELL_PATH=str(launcher))
    return env
