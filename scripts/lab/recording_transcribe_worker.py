"""Run under our isolated home-folder QA directory on the GPU server."""
from pathlib import Path
import json
import os
import subprocess
import time

root=Path(__file__).resolve().parent
os.environ['HF_HOME']=str(root/'cache/huggingface')
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
gpus=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid','--format=csv,noheader'],text=True)
gpu=next((line.split(',')[1].strip() for line in gpus.splitlines() if 'RTX 3060' in line),'')
os.environ['CUDA_VISIBLE_DEVICES']=gpu if gpu else '-1'
from huggingface_hub import snapshot_download
from faster_whisper import WhisperModel

status=root/'transcribe-status.json'
def progress(**data):
    status.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False),flush=True)

progress(stage='preparing',model='large-v3',gpu='RTX 3060' if gpu else 'CPU')
model_dir=snapshot_download('Systran/faster-whisper-large-v3',allow_patterns=['model.bin','config.json','preprocessor_config.json','tokenizer.json','vocabulary.*'],cache_dir=str(root/'cache/huggingface/hub'))
try:
    model=WhisperModel(model_dir,device='cuda' if gpu else 'cpu',compute_type='float16' if gpu else 'int8',cpu_threads=4)
except Exception as error:
    progress(stage='loading',device='CPU',reason=type(error).__name__)
    model=WhisperModel(model_dir,device='cpu',compute_type='int8',cpu_threads=4)
for number in [1,2]:
    target=root/f'source-{number}'
    started=time.time();words=[];segments_out=[]
    segments,info=model.transcribe(str(target/'speech.wav'),language=None,beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
    progress(stage='transcribing',source=number,language=info.language,language_probability=info.language_probability)
    for segment in segments:
        segments_out.append({'start':segment.start,'end':segment.end,'text':segment.text,'no_speech_prob':segment.no_speech_prob,'avg_logprob':segment.avg_logprob})
        words.extend({'text':word.word.strip(),'start':round(word.start,3),'end':round(word.end,3),'conf':round(word.probability,4)} for word in segment.words or [] if word.word.strip())
        progress(stage='transcribing',source=number,language=info.language,seconds=round(segment.end,1),words=len(words))
    result={'language':info.language,'model':'large-v3','words':words,'segments':segments_out,'seconds_taken':round(time.time()-started,1)}
    (target/'transcript.raw.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'transcript.txt').write_text('\n'.join(segment['text'].strip() for segment in segments_out),encoding='utf-8')
    progress(stage='transcribed',source=number,language=info.language,words=len(words),seconds_taken=result['seconds_taken'])
progress(stage='complete')
