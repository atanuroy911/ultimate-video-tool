"""Source-preserving tutorial layouts. This does not detect windows or cursors."""
from __future__ import annotations
from .util import read_json, write_json


def canvas(meta, aspect=None):
    from .compose import FORMATS
    aspect=aspect or meta.aspect
    fmt=dict(FORMATS[aspect])
    # Recording protection must never silently add space to the selected format.
    return fmt


def layout(data,meta):
    """Keep the source intact; captions retain the normal project appearance."""
    fmt=canvas(meta,data['format']['aspect']);data['format']={k:v for k,v in fmt.items() if k!='tag'}
    data['screen_recording']={'graphics':meta.options.recording_edit=='screen'}
    for scene in data['scenes']:
        scene['moves']=[];scene['tx']='cut';scene['transition_in']='cut';scene['transition_effect']='none';scene['camera_move']='none'
        if scene.get('backdrop'):
            scene['backdrop'].update(motion='none',scrim={'kind':'none','strength':0,'ink':'light'})
        # Unreviewed overlays remain inside the picture and clear of the usual
        # bottom captions. Editors can change placement per element.
        scene['stage']=[.05,.08,.9,.65]
        for element in scene['elements']:
            if not element.get('edited'):
                element.update(free=True,x=.5,y=.2,scale=.4)
    data['cues']=[]


def base_plan(project):
    from .schema import Backdrop, Scene, ScenesFile, Scrim
    meta=project.meta();source=next((m for m in meta.media if m.role=='a_roll'),None)
    if source is None:raise RuntimeError('The recording picture is missing. Import a video and keep its original picture before using this edit mode.')
    beats=project.beats().beats
    plan=ScenesFile(theme=meta.theme,planner='rules',scenes=[Scene(id='s1',start=0,beats=[b.id for b in beats],
        archetype='screen',transition_in='cut',transition_effect='none',camera_move='none',
        backdrop=Backdrop(media=source.id,motion='none',offset=0,scrim=Scrim(kind='none',strength=0,ink='light')))])
    return plan


def supporting_graphics(project,plan):
    """Propose restrained text/step diagrams grounded in quoted narration."""
    import json
    from pydantic import BaseModel, Field
    from .ai import complete_json
    from .schema import Keyword, Steps, Step
    class Callout(BaseModel):
        beat:str
        quote:str=Field(min_length=5,max_length=500)
        title:str=Field(min_length=1,max_length=30)
        steps:list[str]=Field(default_factory=list,max_length=4)
    class Proposal(BaseModel):
        callouts:list[Callout]=Field(default_factory=list,max_length=16)
    words=project.transcript().by_id();beats=project.beats().beats
    reading=[{'id':b.id,'text':' '.join(words[wid].text for wid in b.word_ids if wid in words)} for b in beats]
    prompt=('This is a narrated screen tutorial. Keep the screen visible at all times. Suggest a few useful transparent supporting overlays within the original video: '
        'a short heading or 2-4 process steps. Do not transcribe the whole narration again. Do not invent facts, numbers or claims. '
        'Each callout must name one supplied beat and copy a contiguous quote from that beat as evidence. '
        'Use a brief heading; steps may be empty. Leave breathing room: roughly one callout per 20-35 seconds, and none when it adds no useful information.\n'
        +json.dumps(reading,ensure_ascii=False))
    result=complete_json(prompt,Proposal.model_json_schema(),model_cls=Proposal,max_tokens=3000,timeout=180,retries=0)
    by_id={b.id:b for b in beats};texts={b['id']:b['text'] for b in reading};notes=[];last_end=-10
    duration=project.cuts().output_duration
    for item in sorted(result['callouts'],key=lambda item:by_id[item['beat']].start if item['beat'] in by_id else duration+1):
        beat=by_id.get(item['beat']);quote=' '.join(item['quote'].split()).casefold()
        if not beat or quote not in ' '.join(texts[beat.id].split()).casefold() or beat.start<last_end+6:continue
        start=max(0,beat.start);end=min(duration,start+min(10,max(6,beat.end-start)))
        if end-start<2:continue
        common={'at_word':beat.word_ids[0],'start':start,'end':end,'entrance':'blur-slide','id':f'screen-{len(notes)+1}'}
        steps=[s.strip() for s in item.get('steps',[]) if 0<len(s.strip())<=24]
        element=Steps(**common,items=[Step(title=s) for s in steps]) if len(steps)>=2 else Keyword(**common,text=item['title'],style='underline')
        plan.scenes[0].elements.append(element);notes.append({**item,'start':start,'end':end,'element':element.id});last_end=end
    write_json(project.dir/'recording_graphics.json',{'notes':notes,'source':'narration','protected_screen':True})
    return plan
