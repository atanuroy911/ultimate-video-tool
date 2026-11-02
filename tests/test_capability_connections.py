"""Capabilities must survive discovery and use the same editor model on every surface."""
import json


def test_agent_receives_complete_discovery_and_described_tools(ref):
    from vt.direction.agent import run_agent
    seen = []
    def step(system, card, last, working, goal):
        seen.append((system, last, working))
        if len(seen) == 1:
            assert "timeline.edit_scene" in system and "voice.speak_script" in system
            return {"call": {"module": "meta.catalog", "inputs": {"toolbox": "autonomous"}}}
        if len(seen) == 2:
            assert any(m["id"] == "voice.speak_script" for m in last["output"]["modules"])
            return {"call": {"module": "meta.describe", "inputs": {"module_id": "timeline.edit_scene"}}}
        assert "timeline.edit_scene" in working
        props = last["output"]["module"]["inputs"]["properties"]
        assert "split_at" in props["operation"]["enum"] and "time" in props
        return {"finish": "Discovered the editor"}
    result = run_agent(ref, step)
    assert result.ended == "finished" and all(s.ok for s in result.steps)


def test_ollama_sees_whole_schema_and_discovery_result(monkeypatch):
    from vt.direction.agent import ollama_step
    from vt.modules.defs import load
    load()
    asked = []
    def complete(user, schema, **kwargs):
        asked.append(user)
        return {"finish": "done"}
    monkeypatch.setattr("vt.ai.complete_json", complete)
    last = {"output": {"modules": ["x" * 900, "LAST_CAPABILITY"]}}
    ollama_step()("system", "state", last, ["timeline.edit_scene", "plan.edit", "voice.speak_script"], "goal")
    assert "LAST_CAPABILITY" in asked[0]
    assert "voice.speak_script" in asked[0]
    assert "Answer with one call" in asked[0]


def test_director_edits_update_saved_model_and_all_preview_formats(ref):
    from vt.modules.executor import Executor
    from vt.compose import FORMATS
    from vt.util import read_json
    ex = Executor(ref.dir)
    sid = ref.scenes().scenes[0].id
    edit = ex.call("timeline.edit_scene", {"operation":"edit_element", "scene_id":sid, "index":0,
        "patch":{"start":.137,"end":3.337,"x":.3,"opacity":.6}}, caller="director")
    assert edit.ok, edit.fix
    for fmt in FORMATS.values():
        data = read_json(ref.comp_dir / fmt["tag"] / "data.json")
        el = next(e for s in data["scenes"] for e in s["elements"] if e.get("_i") == 0 and s.get("src",s["id"]) == sid)
        assert el["at"] == .137 and el["until"] == 3.337 and el["opacity"] == .6
    split = ex.call("timeline.edit_scene", {"operation":"split_at", "scene_id":sid, "time":.837}, caller="director")
    assert split.ok, split.fix
    assert ref.scenes().scenes[1].start == .837
    assert (ref.dir / "scenes.prev.json").exists()


def test_action_retiming_keeps_selection_index():
    from vt.scene_ops import _requeue
    from vt.schema import Transcript, Word
    tr=Transcript(language="en",words=[Word(id="w1",text="One",start=0,end=.5),Word(id="w2",text="Two",start=1,end=1.5)])
    actions=[{"who":"a","do":"idle","at_word":"w2","start":.2,"end":.4,"_timed":True},
             {"who":"a","do":"idle","at_word":"w1","start":1.1,"end":1.4,"_timed":True}]
    result=_requeue(actions,tr,2)
    assert result == actions


def test_english_examples_and_studio_catalogue_match():
    from vt.planner.catalogue import component_catalogue
    from vt.schema import ELEMENT_MODELS
    catalogue=component_catalogue()
    assert len(catalogue)==len(ELEMENT_MODELS)
    for spec in catalogue:
        assert spec["example"]==spec["starter"]
        assert not any("\u0980"<=c<="\u09ff" for c in json.dumps(spec["example"],ensure_ascii=False))


def test_graphic_fragments_remain_editable_and_visible_in_all_formats(ref):
    from vt.modules.executor import Executor
    from vt.compose import FORMATS
    from vt.util import read_json
    before=sum(len(s.elements) for s in ref.scenes().scenes)
    anchor=ref.transcript().kept()[0].id
    items=[{"type":"shape","shape":"circle","color":"#7c3aed","at_word":anchor,"start":.137,"end":2.337},
           {"type":"bar_chart","bars":[{"label":"A","value":1},{"label":"B","value":2}],"at_word":anchor,"start":.5,"end":3}]
    r=Executor(ref.dir).call("timeline.place",{"fragments":[{"slot_id":"visuals","items":items}]})
    assert r.ok, r.fix
    assert r.output=={"placed":2,"skipped":0}
    assert sum(len(s.elements) for s in ref.scenes().scenes)==before+2
    for fmt in FORMATS.values():
        data=read_json(ref.comp_dir/fmt["tag"]/"data.json")
        circle=next(e for s in data["scenes"] for e in s["elements"] if e["type"]=="shape")
        assert circle["free"] and circle["at"]==.137 and circle["until"]==2.337
    saved=ref.scenes_path.read_bytes()
    bad=Executor(ref.dir).call("timeline.place",{"fragments":[{"slot_id":"bad","items":[items[0],{"type":"not_a_visual","start":1,"end":2}]}]})
    assert not bad.ok and "not_a_visual" in bad.fix
    assert ref.scenes_path.read_bytes()==saved


def test_reusing_graphic_uses_requested_slot_instead_of_original_manual_range(ref):
    from vt.modules.executor import Executor
    sf = ref.scenes()
    scene = sf.scenes[0]
    scene.elements[0].start = .1
    scene.elements[0].end = .9
    ref.save_scenes(sf)
    result = Executor(ref.dir).call("fill.graphic", {
        "scene_id": scene.id,
        "slot": {"id": "later", "start": 2, "end": 4, "impact": {"time": 3}},
    })
    assert result.ok, result.fix
    assert all(item["start"] == 2 and item["end"] == 4 for item in result.output["items"])


def test_manual_visuals_are_never_removed_by_automatic_person_avoidance():
    from vt.compose.composer import _keep_clear_of_people
    from vt.schema import Scene
    sc=Scene(id="s1",beats=["b1"],backdrop={"media":"person"})
    scene={"edited":True,"elements":[{"type":"shape","free":True}]}
    _keep_clear_of_people(scene,sc,{"person":{"w":1080,"h":1920,"faces":[[0,0,1,1]]}},"9:16")
    assert len(scene["elements"])==1


def test_free_scene_split_preserves_actions_without_duplicate_characters():
    from vt.editor_timing import split_at
    from vt.schema import Scene,ScenesFile,Beats,Beat
    sf=ScenesFile(scenes=[Scene(id="s1",beats=["b1"],stick={"cast":[{"id":"a"}],"actions":[{"who":"a","do":"wave","at_word":"w1","start":1,"end":3}]})])
    beats=Beats(beats=[Beat(id="b1",word_ids=["w1"],text="One",start=0,end=4)])
    out=split_at(sf,beats,4,"s1",2,{})
    assert out.scenes[0].stick["actions"][0]["_timed"]
    assert out.scenes[0].stick["actions"][0]["end"]==3
    assert out.scenes[1].stick is None


def test_director_repair_and_scene_merge_do_not_discard_valid_content(ref):
    from vt.script.compile import script_from_scenes,compile_script
    from vt.script.validate import repair_script
    from vt.script.models import VideoScript
    from vt.scene_ops import merge_with_next
    sf=ref.scenes()
    sc=sf.scenes[0]
    sc.elements=[sc.elements[0].model_copy(deep=True) for _ in range(8)]
    sc.sfx=[{"at_word":sc.elements[0].at_word,"id":"pop"} for _ in range(8)]
    data=script_from_scenes(sf).model_dump(by_alias=True)
    fixed=VideoScript.model_validate(repair_script(data,ref.transcript(),ref.beats()))
    assert len(fixed.scenes[0].overlays)==8 and len(fixed.scenes[0].sfx)==8
    compiled=compile_script(fixed,ref.transcript(),ref.beats())
    count=sum(len(s.sfx) for s in compiled.scenes)
    merged=merge_with_next(compiled,ref.beats(),compiled.scenes[0].id)
    assert sum(len(s.sfx) for s in merged.scenes)==count
