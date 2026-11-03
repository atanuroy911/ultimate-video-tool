"""Tutorials must not lose demonstrated material to cropping or automatic cuts."""
from copy import deepcopy
import pytest
from vt.schema import MediaItem, ProjectMeta, Options, Cuts
from vt.screen_recording import canvas, layout


def meta(mode='screen'):
    return ProjectMeta(id='screen-qa',aspect='16:9',options=Options(recording_edit=mode),
        media=[MediaItem(id='aroll',file='media/aroll.mp4',kind='video',role='a_roll',width=1920,height=1080)])


def test_recording_modes_keep_the_selected_canvas():
    for mode in ['subtitles','screen','auto']:
        assert (canvas(meta(mode))['width'],canvas(meta(mode))['height'])==(1920,1080)


def test_source_has_no_camera_motion_and_overlays_stay_in_the_picture():
    data={'format':{'aspect':'16:9'},'scenes':[{'backdrop':{'motion':'pan'},'elements':[{'type':'keyword','text':'Evidence'}]}]}
    layout(data,meta())
    assert 'rail_height' not in data['screen_recording']
    scene=data['scenes'][0]
    assert scene['moves']==[] and scene['camera_move']=='none'
    assert scene['backdrop']['scrim']['strength']==0
    element=scene['elements'][0]
    assert 0<element['y']<.7
    assert data['format']['height']==1080


def test_explicit_manual_placement_survives_the_tutorial_default_layout():
    element={'type':'keyword','text':'Chosen placement','edited':True,'x':.2,'y':.3,'scale':.8}
    data={'format':{'aspect':'16:9'},'scenes':[{'elements':[deepcopy(element)]}]}
    layout(data,meta())
    assert data['scenes'][0]['elements'][0]==element


@pytest.mark.parametrize('mode',['subtitles','screen'])
@pytest.mark.parametrize('caption_style',['theme','pop'])
def test_recording_uses_the_same_captions_as_other_videos(ref,mode,caption_style):
    from vt.compose.composer import compose_project
    from vt.util import read_json
    original=ref.meta().options.model_copy(update={'caption_style':caption_style})
    ref.update_meta(options=original)
    baseline=read_json(compose_project(ref,'16:9').parent/'data.json')
    ref.update_meta(options=original.model_copy(update={'recording_edit':mode}))
    recording=read_json(compose_project(ref,'16:9').parent/'data.json')
    assert recording['format']==baseline['format']
    assert recording['theme']['caption']==baseline['theme']['caption']
    assert recording['captions']==baseline['captions']


def test_video_factory_is_visible_to_the_renderer_media_discovery(ref):
    from vt.compose.composer import write_composition
    from vt.project import load_theme
    from bs4 import BeautifulSoup
    theme=load_theme(ref.meta().theme)
    data={'format':{'width':1920,'height':1080},'duration':8,'media':{'source':{'kind':'video','src':'media/source.mp4'}}}
    index=write_composition(ref.comp_dir/'video-discovery',data,theme)
    scripts=BeautifulSoup(index.read_text(encoding='utf-8'),'html.parser').find_all('script')
    assert any('document.createElement("video")' in script.get_text() for script in scripts if not script.get('src'))


def test_protected_recording_keeps_pauses_but_still_applies_manual_cuts(ref,monkeypatch):
    from vt.pipeline import Pipeline
    from vt import audio_edit as ae
    from vt.stages import audio
    from vt.util import write_json
    ref.update_meta(options=Options(recording_edit='subtitles',remove_fillers=True,remove_retakes=True))
    write_json(ref.dir/'cuts.silence.json',{'cuts':Cuts(source_duration=10,keep=[(5,9)]).model_dump()})
    write_json(ref.raw_transcript_path,{'words':[{'text':'um','start':5,'end':5.5}]})
    write_json(ref.dir/'tighten.json',{'cuts':[{'src':[[6,7]]}]})
    monkeypatch.setattr(ae,'load',lambda p:{'cuts':[[8,9]]})
    monkeypatch.setattr(ae,'apply_to_cut_audio',lambda *args:None)
    monkeypatch.setattr(type(ref),'ensure_preview_audio',lambda self:None)
    import soundfile
    monkeypatch.setattr(soundfile,'info',lambda path:type('Info',(),{'duration':10})())
    monkeypatch.setattr(audio,'apply_cuts',lambda source,cuts,out:cuts.output_duration)
    Pipeline(ref).stage_cuts(force=True)
    assert ref.cuts().keep==[(0,8),(9,10)]
