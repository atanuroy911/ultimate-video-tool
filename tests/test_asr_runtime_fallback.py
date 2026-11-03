from pathlib import Path
import pytest
from vt.stages import asr


def test_late_cuda_decode_failure_restarts_the_whole_transcription_on_cpu(monkeypatch):
    attempts=[];messages=[]
    def decode(path,**options):
        attempts.append(options)
        if options['device']!='cpu':raise RuntimeError('Library libcublas.so.12 is not found or cannot be loaded')
        return {'words':[{'text':'complete result'}]}
    monkeypatch.setattr(asr,'_transcribe',decode)
    result=asr.transcribe(Path('recording.wav'),model='large-v3',language='en',chunks=[(0,10)],progress=lambda *args:messages.append(args))
    assert result['words']==[{'text':'complete result'}]
    assert [item['device'] for item in attempts]==[None,'cpu']
    assert attempts[1]['chunks']==[(0,10)]
    assert any('CPU' in message[2] for message in messages)


@pytest.mark.parametrize('device,message',[('cpu','Library libcudnn.so.9 is missing'),(None,'Invalid audio data')])
def test_cpu_and_unrelated_decode_errors_are_not_hidden(monkeypatch,device,message):
    attempts=[]
    def decode(*args,**options):attempts.append(options);raise RuntimeError(message)
    monkeypatch.setattr(asr,'_transcribe',decode)
    with pytest.raises(RuntimeError,match=message):asr.transcribe(Path('recording.wav'),device=device)
    assert len(attempts)==1
