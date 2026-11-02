import pytest

from vt.editor_timing import move_edge, split_at, resolved_elements
from vt.compose.composer import scene_timing
from vt.schema import ScenesFile, Scene, Beats, Beat


def test_scene_edge_and_split_are_not_bound_to_sentences():
    beats=Beats(beats=[Beat(id="b1",word_ids=["w1"],text="One",start=0,end=3),Beat(id="b2",word_ids=["w2"],text="Two",start=3,end=6)])
    sf=ScenesFile(scenes=[Scene(id="s1",beats=["b1"],elements=[dict(type="title",text="One",at_word="w1")]),Scene(id="s2",beats=["b2"])])
    moved=move_edge(sf,beats,6,"s1",2.137)
    assert scene_timing(moved,beats,6)[0]["end"]==2.137
    assert moved.scenes[0].beats==["b1"] and moved.scenes[1].beats==["b2"]
    split=split_at(moved,beats,6,"s1",.873,{"s1:0":{"start":0,"end":2.137}})
    assert [t["start"] for t in scene_timing(split,beats,6)]==[0,.873,2.137]
    assert split.scenes[1].beats==[]
    assert split.scenes[0].elements[0].end==2.137
    assert len(sf.scenes)==2 and sf.scenes[1].start is None


def test_free_visual_and_caption_changes_reach_all_formats(ref):
    from vt.server.app import edit_element, edit_word, WordEdit, get_scenes, free_scene_edge, TimeBody, free_scene_split
    from vt.compose import FORMATS
    from vt.util import read_json
    sid=ref.scenes().scenes[0].id
    edit_element(ref.id,sid,0,{"start":2.137,"end":7.321,"x":.23,"y":.42,"scale":.7,"rotation":12,"opacity":.6})
    word=ref.transcript().kept()[0]
    edit_word(ref.id,word.id,WordEdit(start=1.237,end=1.937,text="Changed"))
    free_scene_edge(ref.id,sid,TimeBody(t=1.137))
    free_scene_split(ref.id,sid,TimeBody(t=.537))
    for fmt in FORMATS.values():
        data=read_json(ref.comp_dir/fmt["tag"]/"data.json")
        el=data["scenes"][0]["elements"][0]
        assert el["free"] and el["at"]==2.137 and el["until"]==7.321
        assert el["x"]==.23 and el["opacity"]==.6
        cap=next(c for c in data["captions"] if any(w["id"]==word.id for w in c["words"]))
        assert cap["start"]==1.237 and cap["end"]==1.937 and cap["words"][0]["text"]=="Changed"
    assert get_scenes(ref.id)["timing"]["scenes"][1]["start"]==.537
    # A subsequent text correction must keep the independently split empty-beat scene.
    edit_word(ref.id,word.id,WordEdit(text="Again"))
    assert len(ref.scenes().scenes)==4


def test_visual_split_duplicate_remove_and_more_than_five(ref):
    from vt.server.app import edit_element, get_scenes
    sid=ref.scenes().scenes[0].id
    edit_element(ref.id,sid,0,{"start":.137,"end":3.337})
    edit_element(ref.id,sid,0,{"split":1.337})
    a,b=ref.scenes().scenes[0].elements[:2]
    assert a.start==.137 and a.end==b.start==1.337 and b.end==3.337
    for _ in range(5): edit_element(ref.id,sid,0,{"duplicate":True})
    assert len(ref.scenes().scenes[0].elements)>5
    count=len(ref.scenes().scenes[0].elements)
    edit_element(ref.id,sid,1,{"delete":True})
    assert len(ref.scenes().scenes[0].elements)==count-1


def test_every_library_preview_compiles(ref):
    from vt.server.app import element_preview
    from vt.planner.catalogue import component_catalogue
    from vt import paths
    from vt.util import read_json
    for spec in component_catalogue():
        result=element_preview(spec["type"])
        assert result["url"].endswith("index.html")
        data=read_json(paths.PROJECTS/".elements"/spec["type"]/"data.json")
        assert data["scenes"][0]["elements"][0]["type"]==spec["type"]
        assert data["captions_enabled"] is False


def test_manual_timing_ripples_and_undo_restores_original_source_position():
    from vt.editor_timing import retime_manual
    from vt.schema import Cuts
    sf=ScenesFile(scenes=[Scene(id="s1",beats=["b1"],start=0,elements=[dict(type="title",text="Keep me",at_word="w1",start=2.137,end=4.337)]),Scene(id="s2",beats=["b2"],start=3.137)])
    before=Cuts(source_duration=6,keep=[(0,6)])
    after=Cuts(source_duration=6,keep=[(0,1),(1.5,6)])
    moved,clock=retime_manual(sf,before,after,{})
    assert moved.scenes[0].elements[0].start==1.637
    assert moved.scenes[1].start==2.637
    restored,_=retime_manual(moved,after,before,clock)
    assert restored==sf


def test_caption_undo_and_redo_restore_text_and_timing(ref):
    from vt.server.app import edit_word, word_history, WordEdit
    w=ref.transcript().kept()[0]
    edit_word(ref.id,w.id,WordEdit(text=w.text))  # normalize the hand-written fixture through the same edit pipeline
    edit_word(ref.id,w.id,WordEdit(text="Changed",start=2.137,end=2.937))
    word_history(ref.id,"undo")
    original=ref.transcript().by_id()[w.id]
    assert original.text==w.text and original.caption_start is None
    word_history(ref.id,"redo")
    restored=ref.transcript().by_id()[w.id]
    assert restored.text=="Changed" and restored.caption_start==2.137


def test_extract_recording_range_creates_a_real_editable_audio_asset(ref):
    from test_audio_edit import tone_project
    from vt.server.app import extract_voice_clip, RangeBody
    import soundfile as sf
    import numpy as np
    tone_project(ref)
    result=extract_voice_clip(ref.id,RangeBody(start=2.137,end=3.337))
    media=next(m for m in ref.meta().sounds if m.id==result["id"])
    import subprocess
    from vt.util import find_tool
    raw=subprocess.run([find_tool("ffmpeg"),"-v","error","-i",str(ref.dir/media.file),"-f","f32le","-ac","1","-ar","16000","pipe:1"],capture_output=True,check=True).stdout
    samples=np.frombuffer(raw,dtype="float32")
    assert len(samples)/16000==pytest.approx(1.2,abs=.03)
    assert np.max(np.abs(samples))>.1
