import pytest
from pydantic import ValidationError
from vt.schema import Cartoon
from vt.modules.defs.styles import StoryKitIn, story_kit


def test_story_kit_matches_renderer_contract():
    kit = story_kit(None, StoryKitIn())
    assert kit.character_styles == ['classic', 'ink', 'paper']
    assert len(kit.environments) == 10
    assert kit.text_treatments == ['sign', 'chalk', 'paint', 'neon']
    from pathlib import Path
    renderer = (Path(__file__).resolve().parents[1] / 'server' / 'renderer' / 'runtime' / 'vt-cartoon.js').read_text(encoding='utf-8')
    for env in kit.environments:
        assert f'{env}: (g)' in renderer


def test_story_controls_roundtrip_without_losing_legacy_data():
    old = Cartoon(at_word='w1',cast=[{'who':'teacher','name':'Sam'}],set='classroom')
    assert old.camera == 'push'
    new = old.model_copy(update={'character_style':'ink','lighting':'sunset','camera':'pan'})
    data = new.model_dump()
    data['artifacts'] = [{'media':'generated-prop','x':.3,'y':.65,'width':.15,'height':.25,'depth':'behind','rotation':-15}]
    data['labels'] = [{'text':'One step','treatment':'chalk','x':.5,'y':.2,'width':.4,'rotation':0}]
    assert Cartoon.model_validate(data).model_dump() == data


@pytest.mark.parametrize('field,value', [('x',-1),('height',0),('width',2),('rotation',999)])
def test_artifact_bounds_are_validated(field, value):
    with pytest.raises(ValidationError):
        Cartoon(at_word='w1',cast=[{'who':'robot'}],artifacts=[{'media':'prop',field:value}])


def test_automatic_story_keeps_grounded_timing_and_editable_cast():
    from vt.script.models import VideoScript
    from vt.script.compile import compile_script
    from vt.script.story_kit import apply_story_kit
    from vt.schema import Transcript, Word, Beats, Beat
    tr=Transcript(words=[Word(id='w0',text='Sam',start=0,end=.4),Word(id='w1',text='waves',start=.5,end=1)])
    beats=Beats(beats=[Beat(id='b1',word_ids=['w0','w1'],start=0,end=2,text='Sam waves')])
    script=VideoScript.model_validate({'kind':'cartoon','cast':[{'id':'sam','name':'Sam','role':'teacher'}],
        'sets':[{'id':'class','kind':'classroom'}], 'scenes':[{'id':'s1','beats':['b1'],'set':'class',
        'actions':[{'who':'sam','do':'wave','at_word':'w1'}]}]})
    original=compile_script(script,tr,beats)
    assert apply_story_kit(original.model_copy(deep=True),script,tr,beats,'illustrated') == original
    changed=apply_story_kit(original.model_copy(deep=True),script,tr,beats,'ink')
    el=changed.scenes[0].elements[0]
    assert el.character_style=='ink' and el.set=='classroom'
    assert el.cast[0].name=='Sam' and el.cast[0].who=='teacher'
    assert el.cues[0].start==.5 and el.cues[0].pose=='wave'
    assert changed.scenes[0].stick is None and changed.scenes[0].beats==['b1']


def test_cartoon_action_rejects_backwards_timing():
    with pytest.raises(ValidationError):
        Cartoon(at_word='w1',cast=[{}],cues=[{'start':3,'end':2}])
