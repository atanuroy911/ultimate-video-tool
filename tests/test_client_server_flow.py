import threading
import pytest
from vt import directors,paths
from vt.engines import setup,installers,placement


def test_storage_paths_belong_to_processing_server(tmp_path,monkeypatch):
    monkeypatch.setattr(paths,'SETTINGS',tmp_path/'settings.json')
    setup.save(install_dir=str(tmp_path/'programs'),models_dir=str(tmp_path/'models'))
    inst=installers.ComfyInstaller()
    assert inst.root==tmp_path/'programs/comfyui'
    assert inst.models==tmp_path/'models/comfyui'
    with pytest.raises(ValueError,match='processing server'):
        setup.save(models_dir='client-relative-folder')
    config=setup.state()
    options=setup.install_options('comfy',['pictures'],config)
    setup.save(install_dir=str(tmp_path/'later-change'))
    assert options['root']==tmp_path/'programs/comfyui'
    assert options['port']>=placement.OWN_BASE['comfy']


def test_codex_and_claude_share_one_client_but_route_independently():
    broker=directors.DirectorBroker();sent=[]
    broker.connect('home','Home PC',assistant='claude',logged_in=True,send=sent.append)
    broker.connect('home','Home PC',assistant='codex',logged_in=True,send=sent.append)
    assert {d.id for d in broker.devices()}=={'claude@home','codex@home'}
    result={}
    thread=threading.Thread(target=lambda:result.update(broker.request('home','demo','Direct',1,assistant='codex')));thread.start()
    for _ in range(100):
        if sent:break
        threading.Event().wait(.005)
    assert sent[0]['assistant']=='codex'
    broker.finish(sent[0]['request'],ok=True);thread.join(1)
    assert result['ok']
    broker.disconnect('home');assert broker.devices()==[]


def test_new_comfy_install_uses_selected_gpu_and_best_fitted_picture_files(tmp_path,monkeypatch):
    from vt.engines import hardware
    monkeypatch.setattr(paths,'SETTINGS',tmp_path/'settings.json')
    monkeypatch.setattr(paths,'DATA',tmp_path)
    monkeypatch.setattr(hardware,'detect',lambda:{'ram_gb':32,'gpus':[{'index':1,'name':'RTX 3060','memory_gb':12,'compute':8.6}]})
    options=setup.install_options('comfy',['pictures'],{'install_dir':str(tmp_path/'programs'),'models_dir':str(tmp_path/'models'),'gpu':1})
    assert options['recipe']=='klein-4b'
    inst=installers.ComfyInstaller(**options)
    assert inst.gpu==1
    assert any(x['path'].endswith('flux-2-klein-4b.safetensors') for x in inst.manifest())
    assert not any(x['path'].endswith('z_image_turbo_bf16.safetensors') for x in inst.manifest())


def test_other_clients_cannot_finish_a_run_and_a_computer_that_never_returns_releases_it():
    broker=directors.DirectorBroker(grace=0);sent=[];result={}
    broker.connect('home','Home',logged_in=True,send=sent.append)
    thread=threading.Thread(target=lambda:result.update(broker.request('home','demo','Direct',10)))
    thread.start()
    for _ in range(100):
        if sent:break
        threading.Event().wait(.005)
    assert not broker.finish(sent[0]['request'],ok=True,device_id='another-device')
    broker.disconnect('home');thread.join(1)
    assert not thread.is_alive() and result['ok'] is False and 'lost its connection' in result['reason']
