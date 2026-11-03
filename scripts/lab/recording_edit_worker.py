"""Prepare editable projects and render the four requested screen-recording edits."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import time

root=Path(__file__).resolve().parent
os.environ.update(VT_DATA=str(root.parent/'data'),PYTHONPATH=str(root.parent/'app'),
    PATH=str(root.parent/'node/bin')+':/usr/bin:/bin',TMPDIR=str(root.parent/'tmp'),XDG_CACHE_HOME=str(root.parent/'cache'),
    HYPERFRAMES_NO_TELEMETRY='1',DO_NOT_TRACK='1',VT_RENDER_WORKERS='2',OMP_NUM_THREADS='4')
import sys
sys.path.insert(0,str(root.parent/'app'))
from vt.project import Project
from vt.pipeline import Pipeline,compose_all,export
from vt.schema import Cuts,Keyword,Steps,Step
from vt.util import read_json,write_json
from vt.screen_recording import base_plan
from vt.render.hyperframes import snapshot

parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');parser.add_argument('--refresh-previews',action='store_true');parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
def status(**value):
    write_json(root/'render-status.json',value);print(json.dumps(value,ensure_ascii=False),flush=True)
def norm(text):return re.sub(r'[^a-z0-9]+','',text.casefold())


def correct(raw):
    raw=copy.deepcopy(raw);changes=[];words=raw['words']
    for index,word in enumerate(words):
        before=word['text'];token=norm(before)
        after={'cloud':'Claude','plot':'Claude','ral':'RARL','rarl':'RARL','chatgpt':'ChatGPT','gpt':'GPT','gpu':'GPU','ai':'AI','copilot':'Copilot','gemini':'Gemini','tensorflow':'TensorFlow','tensorboard':'TensorBoard'}.get(token)
        if token=='production' and any('abstract' in norm(w['text']) for w in words[max(0,index-20):index]):after='introduction'
        if after:
            punctuation=re.search(r'[^\w]+$',before)
            after+=punctuation.group() if punctuation else ''
            if after!=before:word['text']=after;changes.append({'at':word['start'],'before':before,'after':after})
    for index in range(len(words)-2):
        if [norm(w['text']) for w in words[index:index+3]]==['autunno','shubham','rai']:
            for word,text in zip(words[index:index+3],['Atanu','Shuvam','Roy']):
                changes.append({'at':word['start'],'before':word['text'],'after':text,'evidence':'Author name on the supplied PDF recording at 65 seconds'})
                word['text']=text
    return raw,changes


def locate(words,phrase):
    target=[norm(word) for word in phrase.split()];tokens=[norm(word.text) for word in words]
    for index in range(len(tokens)-len(target)+1):
        if tokens[index:index+len(target)]==target:return words[index]
    raise ValueError('Narration anchor not found: '+phrase)


ANNOTATIONS={
1:[('there is no going back','Use AI. Keep your judgement.',[]),
   ('this is the volume one','Write Like a Researcher',[]),
   ('the foundations','The research workflow',['Foundations','Build the argument','Show evidence','Human–AI workflow']),
   ('the anatomy of a paper','Structure your paper',[]),
   ('display your graphs','Make evidence easy to read',[]),
   ('there is a master prompt','Start with a better prompt',[]),
   ('correct every single line','Human review matters',['Read','Verify','Correct']),
   ('click read now','Read online · Download PDF',[])],
2:[('controlling these tools','Control the tool.',[]),
   ('the second part of the book','Train Like an Engineer',[]),
   ('the foundations','From ideas to a paper',['Foundations','Build the argument','Show your work']),
   ('master prompt','Prompts + a complete rulebook',[]),
   ('how to survive long runs','Build reliable training runs',[]),
   ('resumability','Reliable experiments',['Resume','Monitor','Manage memory']),
   ('reproduce your results','Keep experiments reproducible',['Reproduce','Resume','Schedule']),
   ('no gpu time is wasted','Make GPU time count',[]),
   ('we currently have','Follow RARL for resources',[])]}

manifest=read_json(root/'edits.json',{}) or {}
for source in [1,2]:
    source_dir=root/f'source-{source}'
    raw,corrections=correct(read_json(source_dir/'transcript.raw.json'))
    write_json(source_dir/'caption-corrections.json',corrections)
    for mode in ['subtitles','screen']:
        key=f'{source}-{mode}'
        if key not in manifest:
            status(stage='preparing',source=source,mode=mode)
            title=('Write Like a Researcher' if source==1 else 'Research and engineering guides')+(' · Subtitles' if mode=='subtitles' else ' · Motion graphics')
            pid=f'qa-recording-{source}-{mode}-20261103'
            p=Project(pid)
            if p.exists() and (p.scenes() is not None or p.meta().title!=title):raise RuntimeError('Refusing to overwrite an existing edited project: '+pid)
            if not p.exists():p=Project.create(title,source_dir/'original.mp4',pid=pid,language=raw['language'],aspect='16:9',theme='paper',
                options={'recording_edit':mode,'remove_fillers':False,'remove_retakes':False,'target_length':'keep','caption_style':'theme','aroll':'auto',
                    'music':None,'sfx':False,'sfx_level':'off','motion':'subtle','beat_sync':False,'sound_events':'off','speakers':'off','asr_model':'large-v3'})
            pipe=Pipeline(p);pipe.stage_preprocess()
            import soundfile
            duration=soundfile.info(str(p.master)).duration
            write_json(p.cuts_path,Cuts(source_duration=duration,keep=[(0,duration)]).model_dump())
            shutil.copyfile(p.master,p.cut_audio);write_json(p.raw_transcript_path,raw)
            p.mark_stage('asr','large-v3-reviewed',model='large-v3',words=len(raw['words']))
            pipe.stage_words();pipe.stage_aroll()
            plan=base_plan(p);notes=[]
            if mode=='screen':
                words=p.transcript().kept()
                for index,(phrase,label,steps) in enumerate(ANNOTATIONS[source]):
                    anchor=locate(words,phrase);start=max(0,anchor.start-.12);end=min(duration,start+(10 if steps else 8))
                    common={'id':f'support-{index+1}','at_word':anchor.id,'start':start,'end':end,'entrance':'blur-slide'}
                    element=Steps(**common,items=[Step(title=text) for text in steps]) if steps else Keyword(**common,text=label,style='underline')
                    plan.scenes[0].elements.append(element);notes.append({'element':element.id,'label':label,'anchor':phrase,'start':start,'end':end})
            p.save_scenes(plan);write_json(p.dir/'recording_graphics.json',{'notes':notes,'source':'reviewed narration','protected_screen':True})
            write_json(p.dir/'source.json',{'mode':'video','content_kind':'screen','has_picture':True,'width':1920,'height':1080})
            write_json(p.dir/'caption-corrections.json',corrections)
            compose_all(p);p.update_meta(status='planned')
            manifest[key]={'project':p.id,'source':source,'mode':mode,'duration':duration,'annotations':notes,'caption_corrections':len(corrections),
                'source_sha256':hashlib.file_digest((source_dir/'original.mp4').open('rb'),'sha256').hexdigest()}
            write_json(root/'edits.json',manifest)
        item=manifest[key];p=Project(item['project'])
        if item.get('layout_revision')!='original-canvas-v2':
            # Owner correction: ordinary captions over the original 1920x1080
            # video. No extra band, special caption theme or eight-word grouping.
            options=p.meta().options.model_copy(update={'caption_style':'pop'})
            p.update_meta(options=options)
            plan=p.scenes()
            if mode=='screen':
                notes={note['element']:note for note in item['annotations']}
                for scene in plan.scenes:
                    revised=[]
                    for element in scene.elements:
                        note=notes.get(element.id)
                        if note is None:raise RuntimeError('Unrecognized QA element; refusing to replace it')
                        # A compact transparent heading in the unused Acrobat
                        # side pane, instead of a wide process card below it.
                        revised.append(Keyword(id=element.id,at_word=element.at_word,start=element.start,end=element.end,
                            entrance=element.entrance,text=note['label'],style='underline',edited=True,
                            x=.82,y=.5,scale=.25,ink='#ffffff',text_style='plain'))
                    scene.elements=revised
                p.save_scenes(plan)
            if item.get('export'):item.setdefault('superseded_exports',[]).append(item.pop('export'))
            item.pop('previews',None);item['layout_revision']='original-canvas-v2'
            compose_all(p);write_json(root/'edits.json',manifest)
        if args.refresh_previews or not item.get('previews'):
            compose_all(p)
            times=[65,150,280] if source==1 else [75,205,290]
            if mode=='screen':times=[item['annotations'][index]['start']+2 for index in [1,2,5]]
            folder=root/'previews'/key
            frames=snapshot(p.comp_dir/'16x9',folder,times,gpu=False)
            item['previews']=[str(frame) for frame in frames];item['preview_times']=times
            write_json(root/'edits.json',manifest)
        if args.smoke and key=='1-subtitles':
            status(stage='testing-video-render',project=p.id)
            from vt.compose.composer import write_composition
            from vt.render.hyperframes import render_silent
            from vt.util import run,find_tool
            data=read_json(p.comp_dir/'16x9/data.json');original=p.comp_dir/'16x9'
            data['duration']=8
            for scene in data['scenes']:
                scene.update(start=0,end=8,elements=[])
                if scene.get('backdrop'):scene['backdrop']['offset']=60
            data['captions']=[];data['cues']=[];data['layers']=[]
            for media in data['media'].values():media['_abs']=str(original/media['src'])
            smoke=root/'render-smoke';write_composition(smoke,data,p.theme(p.scenes().theme or p.meta().theme),'Recording video render check')
            result=smoke/'sample.mp4';render_silent(smoke,result,workers=2,gpu=False,fps=30)
            import subprocess,numpy as np
            def frame(path,at,filter_):
                value=subprocess.check_output([find_tool('ffmpeg'),'-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-vf',filter_,'-f','rawvideo','-pix_fmt','rgb24','-'])
                return np.frombuffer(value,dtype=np.uint8).astype(float)
            expected=frame(source_dir/'original.mp4',61,'scale=1920:1080')
            actual=frame(result,1,'crop=1920:1080:0:0')
            difference=float(np.abs(expected-actual).mean());write_json(root/'render-smoke.json',{'mean_absolute_source_error':difference,'file':str(result)})
            if difference>8:raise RuntimeError(f'The source picture did not survive the real render: pixel error {difference:.2f}')
            status(stage='video-render-passed',mean_absolute_source_error=difference)
        if args.render and not item.get('export'):
            status(stage='rendering',source=source,mode=mode,project=p.id)
            last=[0.]
            def progress(stage,fraction,message):
                if time.monotonic()-last[0]>4 or fraction>=1:
                    status(stage=stage,fraction=round(fraction,3),message=message,source=source,mode=mode,project=p.id);last[0]=time.monotonic()
            result=export(p,'16:9',fps=30,gpu=False,quality='looks',progress=progress)
            item['export']=result['video'];item['srt']=result['srt'];write_json(root/'edits.json',manifest)
status(stage='complete' if args.render else 'prepared',projects=manifest)
