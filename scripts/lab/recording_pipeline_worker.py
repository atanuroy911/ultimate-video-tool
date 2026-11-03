"""Run the actual product pipeline and export for the four recording QA projects."""
from pathlib import Path
import json
import argparse
import os
import shutil
import subprocess
import sys
import time

root=Path(__file__).resolve().parent
product=root.parent
os.environ.update(VT_DATA=str(product/'data'),PYTHONPATH=str(product/'app'),
    PATH=str(product/'node/bin')+':/usr/bin:/bin',TMPDIR=str(product/'tmp'),XDG_CACHE_HOME=str(product/'cache'),
    HF_HOME=str(root/'cache/huggingface'),HF_HUB_DISABLE_XET='1',HF_HUB_DISABLE_TELEMETRY='1',
    HYPERFRAMES_NO_TELEMETRY='1',DO_NOT_TRACK='1',VT_RENDER_WORKERS=str(min(4,os.cpu_count() or 2)),OMP_NUM_THREADS='4')
gpus=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid','--format=csv,noheader'],text=True)
os.environ['CUDA_VISIBLE_DEVICES']=next((line.split(',')[1].strip() for line in gpus.splitlines() if 'RTX 3060' in line),'-1')
os.environ.update(CUDA_DEVICE_ORDER='PCI_BUS_ID',ANGLE_PREFERRED_DEVICE='NVIDIA GeForce RTX 3060')
sys.path.insert(0,str(product/'app'))
from vt.project import Project
from vt.pipeline import Pipeline,export
from vt.util import read_json,write_json
parser=argparse.ArgumentParser();parser.add_argument('--smoke-only',action='store_true');parser.add_argument('--gpu-smoke',action='store_true');args=parser.parse_args()

manifest=read_json(root/'edits.json',{}) or {}
def status(**value):
    write_json(root/'render-status.json',value)
    print(json.dumps(value,ensure_ascii=False),flush=True)

def check_export_picture(file,source,duration):
    """Reject a frozen/missing source before publishing a finished-file link."""
    from vt.util import find_tool
    import numpy as np
    def picture(path,at):
        raw=subprocess.check_output([find_tool('ffmpeg'),'-v','error','-ss',str(at),'-i',str(path),'-frames:v','1',
            '-vf','crop=iw:trunc(ih*0.7/2)*2:0:0,scale=480:-2','-pix_fmt','rgb24','-f','rawvideo','-'])
        return np.frombuffer(raw,dtype=np.uint8).astype(float)
    original=root/f'source-{source}/original.mp4'
    errors={str(t):float(np.abs(picture(file,t)-picture(original,t)).mean()) for t in [5,65,150,min(280,duration-5)]}
    write_json(Path(file).with_suffix('.source-check.json'),{'source_frame_errors':errors,'maximum_allowed':8})
    if max(errors.values())>=8:raise RuntimeError('Rendered source picture failed QA: '+str(errors))
    return errors

if args.smoke_only:
    from vt.compose.composer import compose_project,write_composition
    from vt.render.hyperframes import render_silent
    from vt.util import find_tool
    import numpy as np
    p=Project('qa-recording-1-subtitles-20261103')
    original=compose_project(p,'16:9').parent
    data=read_json(original/'data.json');data['duration']=8
    data['captions']=[];data['layers']=[];data['cues']=[]
    for scene in data['scenes']:
        scene.update(start=0,end=8,elements=[]);scene['backdrop']['offset']=60
    for media in data['media'].values():media['_abs']=str(original/media['src'])
    smoke=root/'render-smoke'
    write_composition(smoke,data,p.theme(p.scenes().theme or p.meta().theme),'Real video-frame regression')
    status(stage='testing-video-render')
    out=smoke/('sample-gpu.mp4' if args.gpu_smoke else 'sample.mp4')
    if args.gpu_smoke:
        from vt.render.hyperframes import hyperframes_cmd
        from vt.render.browser_gpu import nvidia_render_device,browser_environment
        from vt.util import run
        selected=nvidia_render_device()
        if not selected:raise RuntimeError('No usable GPU encoder was found; hardware verification cannot pass')
        os.environ.update(browser_environment(smoke/'.renderer',selected))
        os.environ.update(PRODUCER_BROWSER_GPU_MODE='hardware',PRODUCER_ALLOW_SOFTWARE_FALLBACK='false',PRODUCER_ALLOW_SOFTWARE_WEBGPU='false')
        log=root/'gpu-check/browser-render.log'
        with log.open('w') as stream:
            run(hyperframes_cmd('render',str(smoke),'-o',str(out),'-f','30','-q','looks','-w','2','--gpu','--browser-gpu','--no-best-effort','--video-frame-format','png','--debug'),
                on_line=lambda line:stream.write(line+'\n'),stall_seconds=120)
    else:render_silent(smoke,out,gpu=True,fps=30)
    def frame(file,t):
        raw=subprocess.check_output([find_tool('ffmpeg'),'-v','error','-ss',str(t),'-i',str(file),'-frames:v','1','-vf','scale=480:270','-f','rawvideo','-pix_fmt','rgb24','-'])
        return np.frombuffer(raw,dtype=np.uint8).astype(float)
    errors={str(t):float(np.abs(frame(out,t)-frame(root/'source-1/original.mp4',60+t)).mean()) for t in [1,7]}
    write_json(root/'render-smoke.json',{'errors':errors,'file':str(out)})
    if max(errors.values())>=8:raise RuntimeError('Real video frame regression failed: '+str(errors))
    status(stage='video-render-passed',errors=errors)
    sys.exit(0)

for source in [1,2]:
    for mode in ['subtitles','screen']:
        key=f'{source}-{mode}'
        pid=f'qa-recording-{source}-{mode}-20261103'
        title=('Write Like a Researcher' if source==1 else 'Research and engineering guides')+(' · Subtitles' if mode=='subtitles' else ' · Motion graphics')
        p=Project(pid)
        if not p.exists():
            p=Project.create(title,root/f'source-{source}/original.mp4',pid=pid,language='en',aspect='16:9',theme='paper')
        if p.meta().title!=title:raise RuntimeError('Refusing to alter an unrelated project: '+pid)
        item=manifest.setdefault(key,{'project':pid,'source':source,'mode':mode})
        options=p.meta().options.model_copy(update={'recording_edit':mode,'caption_style':'pop','aroll':'auto','look':'classic',
            'remove_fillers':False,'remove_retakes':False,'target_length':'keep','music':None,'sfx':False,'sfx_level':'off',
            'motion':'subtle','beat_sync':False,'sound_events':'off','speakers':'off','asr_model':'large-v3'})
        p.update_meta(options=options)
        last=[0.]
        def progress(stage,fraction,message):
            if time.monotonic()-last[0]>3 or fraction in (0,1):
                status(project=pid,source=source,mode=mode,stage=stage,fraction=round(fraction,3),message=message)
                last[0]=time.monotonic()
        if item.get('pipeline_revision')!='full-pipeline-original-canvas-v1':
            # Retire the custom preparation plan. The production plan stage
            # must make the plan, and production ASR must process the input.
            if p.scenes_path.exists():
                backup=p.dir/'scenes.before-full-pipeline.json'
                if not backup.exists():shutil.copyfile(p.scenes_path,backup)
                p.scenes_path.unlink()
            Pipeline(p,progress=progress).run()
            if not p.scenes():raise RuntimeError('Pipeline did not produce an editable plan')
            if mode=='screen' and not any(s.elements for s in p.scenes().scenes):
                raise RuntimeError('Pipeline produced no motion graphics; inspect ai_notice.json before accepting this version')
            item.update(pipeline_revision='full-pipeline-original-canvas-v1',layout_revision='original-canvas-v2',
                duration=p.cuts().output_duration,annotations=[e.model_dump(exclude_none=True) for s in p.scenes().scenes for e in s.elements])
            if item.get('export'):item.setdefault('superseded_exports',[]).append(item.pop('export'))
            item.pop('previews',None)
            write_json(root/'edits.json',manifest)
        if item.get('export') and item.get('export_revision')!='video-discovery-v1':
            failed=Path(item.pop('export')).resolve()
            if failed.parent!=p.exports_dir.resolve():raise RuntimeError('Unexpected failed export path')
            rejected=root/'rejected';rejected.mkdir(exist_ok=True)
            if failed.exists():shutil.move(str(failed),str(rejected/failed.name))
            if failed.with_suffix('.srt').exists():shutil.move(str(failed.with_suffix('.srt')),str(rejected/failed.with_suffix('.srt').name))
            item.setdefault('rejected_exports',[]).append(str(rejected/failed.name))
            write_json(root/'edits.json',manifest)
        if not item.get('export'):
            result=export(p,'16:9',fps=30,gpu=True,quality='looks',progress=progress)
            status(stage='checking-export',project=pid)
            errors=check_export_picture(result['video'],source,result['duration'])
            item.update(export=result['video'],srt=result['srt'],export_seconds=result['seconds'],export_revision='video-discovery-v1')
            item['source_frame_errors']=errors
            write_json(root/'edits.json',manifest)
            status(stage='exported',project=pid,file=result['video'])
status(stage='complete',projects={key:{'project':item['project'],'export':item.get('export')} for key,item in manifest.items()})
