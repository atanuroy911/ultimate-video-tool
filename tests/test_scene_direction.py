import copy
import pytest
from fastapi.testclient import TestClient
from vt.direction import editor
from vt.util import write_json


def test_directions_use_saved_provenance_and_reject_stale_edits(ref):
    sid=ref.scenes().scenes[0].id
    write_json(ref.dir/'comfy_stills.json',{'stills':[{'scene':sid,'media':'made','workflow':'klein_t2i','model_label':'FLUX.2 Klein','prompt':'Original picture'}]})
    info=editor.view(ref,sid)
    assert info['history'][0]['model_label']=='FLUX.2 Klein'
    config=editor.SceneDirection.model_validate({**info['direction'],'picture_prompt':'A running person','picture_recipe':'klein-4b'})
    saved=editor.save(ref,sid,config,0)
    assert saved['revision']==1 and saved['direction']['picture_prompt']=='A running person'
    assert saved['history'][0]['prompt']=='Original picture'
    with pytest.raises(ValueError,match='changed elsewhere'):
        editor.save(ref,sid,config,0)


def test_direction_api_and_cli_module_share_data(ref):
    from vt.server.app import app
    from vt.modules.defs.direction import scene_settings,DirectionIn
    from vt.modules.workspace import Workspace
    sid=ref.scenes().scenes[0].id
    response=TestClient(app).get(f'/api/projects/{ref.id}/scenes/{sid}/direction')
    assert response.status_code==200,response.text
    result=scene_settings(Workspace(ref.dir),DirectionIn(scene_id=sid))
    assert result.view==response.json()
    assert TestClient(app).put(f'/api/projects/{ref.id}/scenes/{sid}/direction',json={'revision':0,'direction':{'picture_recipe':'made-up'}}).status_code==422


def test_model_switch_changes_cache_identity_without_changing_prompt_or_seed():
    from vt.comfy import picture_workflow
    from vt.comfy.still import still_key
    one=picture_workflow('zimage-fp8')
    two=picture_workflow('zimage-fp8-small-text')
    assert one.id==two.id
    assert still_key(one,'A running person','9:16',4)!=still_key(two,'A running person','9:16',4)


def test_director_can_only_replace_the_requested_scene(ref):
    from vt.ai.providers import FakeProvider,AIUnavailable
    sid=ref.scenes().scenes[0].id
    original=ref.scenes().model_dump()
    candidate=copy.deepcopy(original['scenes'][0])
    config=editor.SceneDirection(instructions='Keep the information and improve placement')
    provider=FakeProvider([candidate])
    result,who=editor.propose(ref,sid,config,provider)
    assert result.id==sid and who=={'who':'fake','model':'fake'}
    assert ref.scenes().model_dump()==original
    candidate['id']='another-scene'
    with pytest.raises(AIUnavailable):
        editor.propose(ref,sid,config,FakeProvider([candidate,candidate]))


@pytest.mark.parametrize('line',['Run every day','Run'])
def test_voice_replacement_is_one_undo_and_preserves_the_exact_cut_clock(ref,line):
    import numpy as np
    import soundfile as sf
    from vt import voice_edit,layers
    from vt.schema import MediaItem
    sf.write(str(ref.master),np.ones(20*24000,dtype='float32')*.1,24000)
    meta=ref.meta()
    meta.sounds.append(MediaItem(id='newvoice',file='media/newvoice.m4a',kind='audio',duration=1))
    ref.save_meta(meta)
    sid=ref.scenes().scenes[0].id
    before=voice_edit.snapshot(ref)
    cuts=ref.cuts().model_dump()
    scenes=ref.scenes().model_dump()
    from vt.compose.composer import scene_timing
    timing=scene_timing(ref.scenes(),ref.beats(),ref.cuts().output_duration)
    doc={'v':1,'tracks':[{'id':'voice','name':'Voice','kind':'audio','hidden':False,'muted':False,'locked':False}],
         'clips':[{'id':'voiceclip','type':'audio','track':'voice','start':0,'dur':1,'media':'newvoice','in':0,'volume':1,'fade_in':0,'fade_out':0}]}
    clean,errors=layers.validate(doc,ref.cuts().output_duration,layers.media_kinds(ref))
    assert not errors
    voice_edit.apply(ref,clean,0,2,line,sid)
    assert ref.cuts().model_dump()==cuts
    assert ref.scenes().model_dump()==scenes
    assert scene_timing(ref.scenes(),ref.beats(),ref.cuts().output_duration)==timing
    assert layers.load(ref)['clips'][0]['start']==0
    assert any('Run' in w.text for w in ref.transcript().kept())
    voice_edit.undo(ref,sid)
    assert voice_edit.snapshot(ref)==before and ref.cuts().model_dump()==cuts


def test_voice_replacement_rolls_back_captions_and_tracks_if_composing_fails(ref,monkeypatch):
    from vt import voice_edit,layers,pipeline
    before=voice_edit.snapshot(ref)
    calls=[]
    compose=pipeline.compose_all
    def fail_once(project):
        calls.append(project.id)
        if len(calls)==1:
            raise RuntimeError('Renderer unavailable')
        return compose(project)
    monkeypatch.setattr(pipeline,'compose_all',fail_once)
    monkeypatch.setattr(voice_edit,'render_voice',lambda project:None)
    with pytest.raises(RuntimeError,match='Renderer unavailable'):
        voice_edit.apply(ref,layers.load(ref),0,2,'Run',ref.scenes().scenes[0].id,mute=False)
    assert voice_edit.snapshot(ref)==before
    assert len(calls)==2


def test_scene_voice_rejects_missing_scene_and_stale_timing_before_generation(ref):
    from vt.server.app import app
    client=TestClient(app)
    body={'engine':'edge','voice':'en-US-AriaNeural','text':'Run','start':0,'end':1,'scene':'missing'}
    assert client.post(f'/api/projects/{ref.id}/voice/overdub',json=body).status_code==404
    body['scene']=ref.scenes().scenes[0].id
    assert client.post(f'/api/projects/{ref.id}/voice/overdub',json=body).status_code==409


def test_direction_narration_follows_free_scene_timing_not_old_sentence_ownership(ref):
    plan=ref.scenes()
    plan.scenes[1]=plan.scenes[1].model_copy(update={'start':1.5})
    ref.save_scenes(plan)
    expected=' '.join(w.text for w in ref.transcript().kept() if (w.start+w.end)/2<1.5)
    assert editor.view(ref,plan.scenes[0].id)['direction']['narration']==expected
