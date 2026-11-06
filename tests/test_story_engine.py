"""Cartoon 2 (the story engine, vt/story/): words -> rule draft -> scene plan -> composition, a director's story, and the catalog."""
import re

from vt import paths


def test_the_words_become_short_caption_units(ref):
    from vt.story.plan import captions_from_words

    caps = captions_from_words(ref.transcript())
    assert caps and all(c["e"] > c["s"] and c["words"] for c in caps)
    assert all(len(c["t"]) <= 60 for c in caps)
    kept = [w.id for w in ref.transcript().kept()]
    assert [w for c in caps for w in c["words"]] == kept          # every spoken word once, in order


def test_a_story_plan_covers_every_beat_and_shares_one_cast(ref):
    from vt.schema import validate_scenes
    from vt.story.service import plan_story

    sf, how, _ = plan_story(ref)
    assert how == "rules" and sf.scenes and sf.story_cast
    assert validate_scenes(sf, ref.transcript(), ref.beats()) == []
    for sc in sf.scenes:
        assert [e.type for e in sc.elements] == ["story"] and sc.archetype == "story"
    people = {i.char for sc in sf.scenes for i in sc.elements[0].items if i.type == "person" and getattr(i, "char", None)}
    assert people <= set(sf.story_cast)


def test_the_composition_draws_story_scenes_with_the_cast(ref):
    from vt.compose.composer import resolve_composition
    from vt.project import load_theme
    from vt.story.service import plan_story

    sf, _, _ = plan_story(ref)
    m = ref.meta()
    data = resolve_composition(sf, ref.transcript(), ref.beats(), load_theme(sf.theme), m.aspect, 30.0, language="en")
    story = [sc for sc in data["scenes"] if sc.get("story")]
    assert story and all(sc["elements"] == [] for sc in story)
    assert set(data["story_cast"]) == set(sf.story_cast) and "head" in data["story_fonts"]
    assert all("bg" in sc["story"] and isinstance(sc["story"]["items"], list) for sc in story)


def test_a_directors_story_is_checked_then_becomes_the_plan(ref):
    from vt.story.service import plan_story, story_task, submit_story

    sf, _, _ = plan_story(ref)
    ref.save_scenes(sf)
    task = story_task(ref)
    spec = task["current_story"]
    assert task["catalog"]["elements"]["person"] and task["captions"] and spec["scenes"]
    bad = {**spec, "scenes": [{**spec["scenes"][0], "elements": [{"type": "person", "char": "nobody"}]}] + spec["scenes"][1:]}
    r = submit_story(ref, bad)
    assert r["ok"] is False and any("nobody" in e for e in r["errors"])
    spec["scenes"][0]["elements"].append({"type": "icon", "name": "star", "x": 400, "y": 300, "at": spec["scenes"][0]["s"] + 0.2})
    r = submit_story(ref, spec)
    assert r["ok"] is True
    now = ref.scenes()
    assert now.planner == "claude" and any(i.type == "icon" for i in now.scenes[0].elements[0].items)


def test_a_designed_scene_is_checked_in_words():
    from vt.story.plan import check_scene

    errs = check_scene({"bg": {"type": "moon"}, "elements": [{"type": "unicorn"}]}, 2.0, 6.0, {})
    assert errs and any("moon" in e or "background" in e for e in errs)
    assert check_scene({"bg": {"type": "room"}, "elements": [{"type": "icon", "name": "star", "x": 270, "y": 300}]}, 2.0, 6.0, {}) == []


def test_the_catalog_names_everything_the_renderer_draws():
    from vt.story import catalog as SC

    src = (paths.RENDERER / "story" / "src" / "engine" / "elements.tsx").read_text(encoding="utf-8")
    block = re.search(r"export const ELEMENTS: Record<string, R> = \{(.*?)\};", src, re.S).group(1)
    drawn = set(re.findall(r"(\w+):\s*\w+", block))
    assert drawn == set(SC.ELEMENTS)
    bgs = (paths.RENDERER / "story" / "src" / "engine" / "backgrounds.tsx").read_text(encoding="utf-8")
    assert set(re.findall(r"'(\w+)'", re.search(r"BG_TYPES = \[(.*?)\]", bgs).group(1))) == set(SC.BACKGROUNDS)
    assert (paths.RUNTIME / "vt-story.js").exists()


def test_the_studio_reads_the_catalog_and_changes_a_look_everywhere(ref):
    from fastapi.testclient import TestClient

    from vt.server.app import app
    from vt.story.service import plan_story

    sf, _, _ = plan_story(ref)
    ref.save_scenes(sf)
    with TestClient(app) as c:
        cat = c.get("/api/story/catalog").json()
        assert "person" in cat["elements"] and "room" in cat["backgrounds"] and "skin" in cat["character"]
        cast = {k: v.model_dump(exclude_none=True) for k, v in sf.story_cast.items()}
        hero = next(iter(cast))
        cast[hero]["shirt"] = "#123456"
        assert c.put("/api/projects/reference/story-cast", json={"cast": cast}).status_code == 200
        assert ref.scenes().story_cast[hero].shirt == "#123456"
        assert c.put("/api/projects/reference/story-cast", json={"cast": {**cast, hero: {**cast[hero], "skin": "red"}}}).status_code == 422
        assert c.get("/api/projects/reference/story-task").json()["current_story"]["scenes"]


def test_cartoon_1_gets_word_timed_extras_from_the_story_engine():
    from types import SimpleNamespace as W

    from vt.schema import Cartoon
    from vt.story.motifs import extras_for

    words = [W(text=t, start=i * 0.4) for i, t in enumerate("She saved 250 dollars and her heart was racing".split())]
    items = extras_for(words)
    kinds = [i["type"] for i in items]
    assert kinds[0] == "counter" and items[0]["to"] == 250 and items[0]["latin"] is True and items[0]["at"] == 0.8
    assert len(items) <= 2 and all("x" in i and "y" in i for i in items if i["type"] != "particles")
    c = Cartoon(at_word="w1", cast=[{"who": "man"}], extras=items)
    assert c.extras[0].type == "counter"
    assert extras_for([W(text="Hello", start=0.0), W(text="there", start=0.3)]) == []


def test_an_english_story_gets_english_names_and_the_hero_follows_the_pronouns():
    from vt.schema import Transcript, Word
    from vt.story.plan import draft_spec

    text = 'Maya sat on her bed with her phone. Her mother came in. "Did the result come?" she asked. Maya smiled because she passed.'
    words, t = [], 0.0
    for i, w in enumerate(text.split()):
        words.append(Word(id=f"w{i}", text=w, start=round(t, 2), end=round(t + 0.3, 2)))
        t += 0.4
    spec, _ = draft_spec(Transcript(language="en", words=words), t + 1, "en")
    assert spec["characters"]["mother"]["name"] == "Mom"
    assert spec["characters"]["hero"].get("bun") is True                       # she/her: the hero is drawn as a woman


def test_the_ai_designs_scenes_and_a_name_in_place_of_a_cast_id_is_repaired(ref):
    import json

    from vt.ai.providers import FakeProvider
    from vt.story.designer import refine
    from vt.story.plan import draft_spec

    spec, _ = draft_spec(ref.transcript(), 20.0, "en")
    hero = spec["characters"]["hero"]
    hero["name"] = hero.get("name") or "Rafi"

    def answer(system, prompt, schema, images):
        assert "cast_ids" in prompt and "dignity" in system
        win = json.loads(prompt.split("\n", 1)[1])["scene_window"]
        return {"bg": {"type": "room"}, "tag": "A very long label that is a sentence",
                "elements": [{"type": "person", "char": hero["name"], "x": 160, "y": 560, "s": 0.8, "pose": "sit"},
                             {"type": "icon", "name": "star", "x": 400, "y": 300, "at": win[0]}]}
    spec, used = refine(spec, provider=FakeProvider(answer))
    assert used == len(spec["scenes"])
    assert all(e["char"] == "hero" for sc in spec["scenes"] for e in sc["elements"] if e["type"] == "person")
    assert not any(t["tag"].startswith("A very long") for t in spec["tags"])


def test_cartoon_1_extras_never_repeat_what_the_scene_already_shows():
    from types import SimpleNamespace as W

    from vt.story.motifs import extras_for

    words = [W(text=t, start=i * 0.4) for i, t in enumerate("He saved 250 dollars and went at ten o'clock".split())]
    assert extras_for(words, shown=frozenset({"big_number"})) == []                  # the scene has its own number card
    kinds = [(i["type"], i.get("to")) for i in extras_for([W(text=t, start=i * 0.4) for i, t in enumerate("He went at ten o'clock".split())])]
    assert ("clock", None) in kinds and ("counter", 10.0) not in kinds


def test_the_directors_notes_reach_every_ai_director_and_never_reject_a_plan():
    from vt import house_rules as H
    from vt.planner import llm_plan
    from vt.planner.prompt import PLANNER_RULES, SCENE_RULES
    from vt.story import designer

    for r in H.RULES:
        assert r.why and r.say
        if "plan" in r.scopes:
            assert r.say in PLANNER_RULES and r.say in SCENE_RULES and r.say in llm_plan.SYSTEM
        if "story" in r.scopes:
            assert r.say in designer.HOUSE_RULES
    assert not hasattr(H, "problems"), "the notes direct the AI; code does not police the plan with them"
