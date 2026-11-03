"""Run real engine/render checks inside the new install's isolated QA folder."""
from pathlib import Path
import json
import time
import httpx
import soundfile as sf
from vt import tts, voice_edit
from vt.project import Project
from vt.schema import ProjectMeta, Cuts, ScenesFile
from vt.util import write_json
from vt.comfy import ComfyClient, picture_workflow, generate_still
from vt.pipeline import Pipeline, compose_all
from vt.render.hyperframes import snapshot

root=Path('/home/roy/ultimate-video-tool-server')
out=root/'qa';out.mkdir(exist_ok=True)
report={}
def record(name,value):
    report[name]=value
    write_json(out/'result.json',report)
    print(name, json.dumps(value),flush=True)

record('server_ui',{'status':httpx.get('http://127.0.0.1:8790/').status_code,
                    'projects':len(httpx.get('http://127.0.0.1:8790/api/projects').json())})
client=ComfyClient('http://127.0.0.1:8188')
info=client.object_info()
record('comfy',{'status':httpx.get(client.url+'/system_stats').status_code,'nodes':len(info)})
queue=httpx.get(client.url+'/queue').json()
if queue.get('queue_running') or queue.get('queue_pending'):
    raise RuntimeError('ComfyUI is busy; leaving its existing work undisturbed.')
record('best_voice',{'engine':tts.recommended_voice('en')[0],'voice':tts.recommended_voice('en')[1]})
started=time.time()
tts.synth_sentence('comfyvoice','design:A calm, thoughtful woman with a clear voice.','One small step can make a difference.',1,out/'voice.wav',language='en')
record('voice_generated',{'seconds':sf.info(str(out/'voice.wav')).duration,'elapsed':round(time.time()-started,1)})
project=Project('installation-check',out)
project.dir.mkdir(exist_ok=True)
project.save_meta(ProjectMeta(id=project.id,title='Installation check',language='en'))
workflow=picture_workflow(object_info=info)
item,provenance=generate_still(project,client,workflow,'A single small green plant in a white ceramic pot on a clean wooden table, soft sunlight, no text',aspect='9:16',seed=17)
record('picture_generated',{'workflow':workflow.label,'seconds':provenance['seconds_taken'],'file':item.file})
duration=sf.info(str(out/'voice.wav')).duration
import shutil
shutil.copyfile(out/'voice.wav',project.master)
write_json(project.cuts_path,Cuts(source_duration=duration,keep=[(0,duration)]).model_dump())
tokens='One small step can make a difference.'.split()
write_json(project.raw_transcript_path,{'words':[{'text':w,'start':i*duration/len(tokens),'end':(i+1)*duration/len(tokens)} for i,w in enumerate(tokens)]})
Pipeline(project).stage_words()
project.save_scenes(ScenesFile.model_validate({'scenes':[{'id':'s1','beats':[b.id for b in project.beats().beats],
    'backdrop':{'media':item.id},'elements':[]}]}))
voice_edit.render_voice(project)
compose_all(project)
frames=snapshot(project.comp_dir/'9x16',out/'frames',[min(1,duration/2)],gpu=False)
record('renderer',{'frame':str(frames[0]),'bytes':frames[0].stat().st_size})
record('complete',True)
client.close()
