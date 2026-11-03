"""Local composition QA only; does not modify the server's editable projects."""
from pathlib import Path
import os
import shutil
import sys

repo=Path(__file__).resolve().parents[2]
qa=repo/'dist/recording-acceptance'
os.environ['VT_DATA']=str(qa/'local-layout-check')
os.environ.update(HYPERFRAMES_NO_TELEMETRY='1',DO_NOT_TRACK='1')
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(repo/'server'))
from vt.project import Project
from vt.pipeline import Pipeline
from vt.schema import Cuts,MediaItem,Keyword
from vt.screen_recording import base_plan
from vt.compose.composer import compose_project
from vt.render.hyperframes import snapshot
from vt.util import read_json,write_json
import soundfile

p=Project('original-canvas-check')
if not p.exists():
    p=Project.create('Original canvas correction check',repo/'2026-11-02 09-07-50.mp4',pid=p.id,
        language='en',aspect='16:9',theme='paper',options={'recording_edit':'screen','caption_style':'pop','sfx':False,'music':None})
shutil.copyfile(qa/'source-1/speech.wav',p.cut_audio)
duration=soundfile.info(str(p.cut_audio)).duration
write_json(p.cuts_path,Cuts(source_duration=duration,keep=[(0,duration)]).model_dump())
write_json(p.raw_transcript_path,read_json(qa/'source-1/transcript.raw.json'))
Pipeline(p).stage_words()
p.update_meta(media=[MediaItem(id='aroll',file='input.mp4',kind='video',role='a_roll',width=1920,height=1080)])
plan=base_plan(p)
word=next(w for w in p.transcript().kept() if w.start>=57)
plan.scenes[0].elements=[Keyword(id='layout-check',at_word=word.id,start=57,end=66,text='Write Like a Researcher',
    edited=True,x=.82,y=.5,scale=.25,ink='#ffffff',text_style='plain',entrance='blur-slide')]
p.save_scenes(plan)
index=compose_project(p,'16:9')
data=read_json(index.parent/'data.json')
assert (data['format']['width'],data['format']['height'])==(1920,1080)
assert data['theme']['caption']['style']=='pop'
if '--render-smoke' in sys.argv:
    from vt.compose.composer import write_composition
    from vt.render.hyperframes import hyperframes_cmd
    from vt.util import run,find_tool
    import numpy as np
    import subprocess
    data['duration']=8;data['captions']=[];data['layers']=[];data['cues']=[]
    for scene in data['scenes']:
        scene.update(start=0,end=8,elements=[])
        scene['backdrop']['offset']=60
    for media in data['media'].values():media['_abs']=str(index.parent/media['src'])
    smoke=qa/'local-render-smoke'
    write_composition(smoke,data,p.theme(p.scenes().theme or p.meta().theme),'Actual video-frame test')
    out=smoke/'sample.mp4'
    if '--gpu-smoke' in sys.argv:
        from vt.render.hyperframes import render_silent
        render_silent(smoke,out,gpu=True,workers=2,on_progress=lambda f,msg:print(f,msg,flush=True))
    else:
        run(hyperframes_cmd('render',str(smoke),'-o',str(out),'-f','30','-q','looks','-w','2','--no-best-effort','--no-browser-gpu','--video-frame-format','png','--debug'),on_line=print,stall_seconds=120)
    def frame(file,t):
        b=subprocess.check_output([find_tool('ffmpeg'),'-v','error','-ss',str(t),'-i',str(file),'-frames:v','1','-vf','scale=480:270','-pix_fmt','rgb24','-f','rawvideo','-'])
        return np.frombuffer(b,dtype=np.uint8).astype(float)
    errors={str(t):float(np.abs(frame(out,t)-frame(repo/'2026-11-02 09-07-50.mp4',60+t)).mean()) for t in [1,7]}
    write_json(smoke/'pixel-check.json',errors);print('Source-frame errors:',errors,flush=True)
    assert max(errors.values())<8,'Rendered video is frozen, out of sync, or missing'
else:
    print('Capturing original-size video with regular captions and a transparent supporting heading.',flush=True)
    for frame in snapshot(index.parent,qa/'corrected-layout-previews',[59.07,65,150],gpu=False):print(frame)
