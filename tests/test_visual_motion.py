import pytest
from vt.schema import Title, ScenesFile
from vt.visual_motion import validate_points
from vt.layers import validate
from vt.editor_timing import edit_element


def points():
    return [{"time":1,"x":.2},{"time":4,"x":.8,"ease":"linear"}]


def test_visual_and_added_layer_share_validated_motion():
    title=Title(at_word="w1",text="Move",keyframes=points())
    doc={"tracks":[{"id":"v","kind":"visual"}],"clips":[{"id":"c","track":"v","type":"text","text":"Move","start":1,"dur":3,"keyframes":points()}]}
    clean, errors=validate(doc,6,{})
    assert not errors
    assert clean['clips'][0]['keyframes']==[p.model_dump() for p in title.keyframes]


@pytest.mark.parametrize('bad',[[{"time":2},{"time":1}],[{"time":1},{"time":1}],[{"time":float('nan')}],[{"time":1,"scale":0}]])
def test_invalid_motion_is_rejected_before_save(bad):
    with pytest.raises(ValueError): validate_points(bad)


def test_splitting_preserves_absolute_animation_and_moving_shifts_it():
    sf=ScenesFile(scenes=[{"id":"s1","beats":["b1"],"elements":[{"type":"title","at_word":"w1","text":"Move","start":1,"end":4,"keyframes":points()}]}])
    times={"s1:0":{"start":1,"end":4}}
    split=edit_element(sf,'s1',0,{'split':2.137},times)
    assert split.scenes[0].elements[0].keyframes==split.scenes[0].elements[1].keyframes==sf.scenes[0].elements[0].keyframes
    moved=edit_element(sf,'s1',0,{'start':3,'end':6},times)
    assert [p.time for p in moved.scenes[0].elements[0].keyframes]==[3,6]


def test_all_reusable_templates_validate_and_director_sees_same_starters():
    from vt.planner.catalogue import catalogue_summary
    from vt.modules.defs.styles import motion_kit, StoryKitIn
    from vt.schema import Scene
    cat=catalogue_summary()
    for template in cat['templates']:
        Scene(id='s1',beats=['b1'],elements=[template['starter']])
    kit=motion_kit(None,StoryKitIn())
    assert {t['variant'] for t in kit.templates}=={t['variant'] for t in cat['templates']}
    assert kit.recipes==cat['motion']


def test_explicit_motion_survives_automatic_direction_and_off_mode():
    from vt.compose.motion import apply
    import copy
    data={'scenes':[{'id':'s1','start':0,'end':4,'transition_effect':'none','camera_move':'none','elements':[{'type':'title','text':'Test','entrance':'typewriter-moves'}]}]}
    for level in ('auto','subtle','off'):
        scene=apply(copy.deepcopy(data),level,'test')['scenes'][0]
        assert scene['elements'][0]['fx']=='typewriter-moves'
        assert scene['moves']==[] and scene['tx'] is None


def test_voice_cut_retains_motion_points_and_undo_restores_collapsed_points():
    from vt.editor_timing import retime_manual
    from vt.schema import Cuts
    before=Cuts(source_duration=6,keep=[(0,6)])
    after=Cuts(source_duration=6,keep=[(0,1),(3,6)])
    sf=ScenesFile(scenes=[{"id":"s1","beats":["b1"],"elements":[{"type":"title","at_word":"w1","text":"Move","start":0,"end":6,"keyframes":[{"time":0},{"time":1.2},{"time":2.8},{"time":4}]}]}])
    moved,clock=retime_manual(sf,before,after,{})
    assert [p.time for p in moved.scenes[0].elements[0].keyframes]==[0,1,1.001,2]
    restored,_=retime_manual(moved,after,before,clock)
    assert restored==sf
