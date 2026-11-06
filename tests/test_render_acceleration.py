from types import SimpleNamespace
import json
import pytest


@pytest.fixture()
def two_cards(monkeypatch):
    """The V100 and the 3060, both allowed (the person has answered "all")."""
    from vt import gpuassign
    cards=[{'index':0,'name':'Tesla V100','uuid':'GPU-v100','free_gb':16.0,'total_gb':16.0,'load':0.0},
           {'index':1,'name':'RTX 3060','uuid':'GPU-3060','free_gb':12.0,'total_gb':12.0,'load':0.0}]
    monkeypatch.setattr(gpuassign,'_cards',lambda:[dict(c) for c in cards])
    gpuassign.save({'allowed':'all'})


def test_encoder_probe_skips_a_gpu_that_cannot_encode(monkeypatch,two_cards):
    from vt.render import browser_gpu as bg
    monkeypatch.delenv('CUDA_VISIBLE_DEVICES',raising=False)
    monkeypatch.setattr(bg.subprocess,'check_output',lambda *a,**k:'0, Tesla V100, GPU-v100, 16000\n1, RTX 3060, GPU-3060, 12000\n')
    monkeypatch.setattr(bg,'find_tool',lambda name:name)
    tried=[]
    def probe(*args,**kwargs):
        uuid=kwargs['env']['CUDA_VISIBLE_DEVICES'];tried.append(uuid)
        return SimpleNamespace(returncode=0 if uuid=='GPU-3060' else 1,stderr=b'Encoder not supported on this card')
    monkeypatch.setattr(bg.subprocess,'run',probe)
    assert bg.nvidia_render_device()=={'name':'RTX 3060','uuid':'GPU-3060'}
    assert tried==['GPU-v100','GPU-3060']


@pytest.mark.parametrize('selected',['1','GPU-3060'])
def test_explicit_gpu_selection_does_not_probe_another_card(monkeypatch,selected,two_cards):
    from vt.render import browser_gpu as bg
    from vt import gpuassign
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES',selected)
    monkeypatch.setattr(gpuassign,'_PIN',selected)                 # the launcher's own fence
    monkeypatch.setattr(bg.subprocess,'check_output',lambda *a,**k:'0, Tesla V100, GPU-v100, 16000\n1, RTX 3060, GPU-3060, 12000\n')
    monkeypatch.setattr(bg,'find_tool',lambda name:name)
    def probe(*args,**kwargs):
        assert kwargs['env']['CUDA_VISIBLE_DEVICES']=='GPU-3060'
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(bg.subprocess,'run',probe)
    assert bg.nvidia_render_device()['uuid']=='GPU-3060'


def test_linux_launcher_selects_vulkan_without_overriding_explicit_software():
    from vt.render.chrome_gpu_launcher import arguments
    values=['--headless','--use-angle=gl-egl','--remote-debugging-pipe']
    actual=arguments(values)
    assert '--use-angle=vulkan' in actual and '--use-vulkan=native' in actual
    assert '--remote-debugging-pipe' in actual and '--use-angle=gl-egl' not in actual
    software=['--use-angle=swiftshader','--headless']
    assert arguments(software)==software


def test_gpu_fallback_is_reported_to_progress_and_saved(tmp_path,monkeypatch):
    from vt.render import hyperframes as hf,browser_gpu as bg
    monkeypatch.setattr(bg,'nvidia_render_device',lambda:None)
    monkeypatch.setattr(hf,'hyperframes_cmd',lambda *args:list(args))
    out=tmp_path/'out.mp4';attempts=[];messages=[]
    def execute(command,**kwargs):
        attempts.append(command)
        if len(attempts)==1:raise RuntimeError('Graphics driver failed to initialize')
        out.write_bytes(b'finished')
        return ''
    monkeypatch.setattr(hf,'run',execute)
    hf.render_silent(tmp_path,out,on_progress=lambda f,msg:messages.append(msg))
    assert '--gpu' in attempts[0] and '--browser-gpu' in attempts[0]
    assert '--no-browser-gpu' in attempts[1]
    assert any('GPU rendering failed' in msg and 'driver' in msg for msg in messages)
    report=json.loads(out.with_suffix('.acceleration.json').read_text())
    assert report['gpu_requested'] is True and len(report['attempts'])==2
    assert report['warnings']


def test_export_list_hides_incomplete_render_and_exposes_acceleration(ref,monkeypatch):
    from vt.server import app as app_module
    from vt.util import write_json
    ref.exports_dir.mkdir(exist_ok=True)
    (ref.exports_dir/'.render-16x9.mp4').write_bytes(b'not finished')
    final=ref.exports_dir/'ready.mp4';final.write_bytes(b'finished')
    report={'gpu_requested':True,'selected_device':{'name':'RTX 3060','uuid':'GPU-3060'},'warnings':[]}
    write_json(final.with_suffix('.acceleration.json'),report)
    monkeypatch.setattr(app_module,'_retention_summary',lambda _:None)
    monkeypatch.setattr(app_module,'_judges_summary',lambda _:None)
    files=app_module.list_exports(ref.id)
    assert [file['name'] for file in files]==['ready.mp4']
    assert files[0]['acceleration']==report
