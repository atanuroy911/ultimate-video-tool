"""Context: the shared reading of a video. Rules always work; the AI's answer is checked against the transcript and anything not said is refused."""
import time

import pytest

from vt import context as C
from vt.ai import AIUnavailable, FakeProvider
from vt.schema import Transcript, Word
from vt.stages.words import build_beats


def make(text: str, step: float = 0.4):
    toks = text.split()
    ws = [Word(id=f"w{i}", text=t, start=round(i * step, 2), end=round(i * step + step - 0.05, 2), conf=0.95, lang="en") for i, t in enumerate(toks, 1)]
    tr = Transcript(language="en", words=ws)
    return tr, build_beats(tr)


TEXT = ("Over the last year I sold more than 3000 products on Amazon and eBay. Amazon pays the best fees. "
        "First, find a product that people want. Then check the price on eBay. And the profit is real! "
        "Now let's talk about shipping. Shipping costs matter. Turkey was my first market. We ate turkey at the end.")


def test_rules_read_topic_entities_facts_and_sections():
    tr, beats = make(TEXT)
    c = C.rules_context(tr, beats, "en")
    assert c.source == "rules" and c.topic.startswith("about ") and "e-commerce" in c.domain and c.mood in C.MOODS
    names = {C._key(e.name) for e in c.entities}
    assert "amazon" in names and "ebay" in names                                       # a capital inside (eBay) counts as a name; Amazon is said twice
    assert "we" not in names and "now" not in names and "first" not in names           # function words are never names
    assert [s.beat for s in c.sentences] == [b.id for b in beats.beats]
    assert any(f.kind == "number" and "3000" in f.text.replace(",", "") for f in c.facts)
    s0 = c.sentence(beats.beats[0].id)
    assert s0.role in C.ROLES and 0 <= s0.importance <= 3
    assert any(s.relation == "continues" for s in c.sentences)                         # "And the profit is real!"
    assert c.sections and c.sections[0].start_beat == beats.beats[0].id and c.sections[-1].end_beat == beats.beats[-1].id
    assert c.to_brief()["mood"] in C.MOODS and c.to_brief()["topic"]


def test_the_reference_project_in_bangla_is_read_without_trouble(ref):
    c = C.rules_context(ref.transcript(), ref.beats(), "bn")
    assert c.sentences and len(c.sentences) == len(ref.beats().beats) and c.sections
    C.save(ref, c)
    assert C.load(ref).topic == c.topic


def ai_reply(beats, tr, **over):
    ids = [b.id for b in beats.beats]
    amazon = next(w.id for w in tr.words if w.text.startswith("Amazon"))
    ebay = next(w.id for w in tr.words if w.text.startswith("eBay"))
    r = {"topic": "selling products online", "summary": "The speaker sells products on Amazon and eBay.", "domain": ["e-commerce"], "mood": "business",
         "entities": [{"name": "Amazon", "type": "company", "word_ids": [amazon], "note": "a marketplace"}, {"name": "eBay", "type": "company", "word_ids": [ebay]}],
         "sentences": [{"beat": ids[0], "idea": "what was sold and where", "importance": 3, "relation": "none", "intent": "boxes of products"}],
         "sections": [{"start_beat": ids[0], "end_beat": ids[-1], "title": "Selling online"}]}
    r.update(over)
    return r


def test_the_ai_answer_improves_the_reading_and_every_claim_is_checked():
    tr, beats = make(TEXT)
    c = C.build(tr, beats, "en", provider=FakeProvider([ai_reply(beats, tr)]))
    assert c.source == "ai" and c.topic == "selling products online" and c.mood == "business"
    assert c.entity("Amazon").type == "company" and c.entity("Amazon").source == "ai" and c.entity("eBay").type == "company"
    s0 = c.sentence(beats.beats[0].id)
    assert s0.idea == "what was sold and where" and s0.importance == 3 and s0.intent == "boxes of products" and s0.source == "ai"
    assert c.sections[0].title == "Selling online"
    # the AI claims an entity at words where it is not said, and a sentence that does not exist: refused (and the retry too)
    amazon = next(w.id for w in tr.words if w.text.startswith("Amazon"))
    bad = ai_reply(beats, tr, entities=[{"name": "Google", "type": "company", "word_ids": [amazon]}], sentences=[{"beat": "b99", "idea": "x", "importance": 1}])
    c2 = C.build(tr, beats, "en", provider=FakeProvider([bad, bad]))
    assert c2.source == "rules" and c2.entity("Google") is None and any("skipped" in n for n in c2.notes)
    # no AI at all: the rules reading stands and the reason is noted
    c3 = C.build(tr, beats, "en", provider=FakeProvider([AIUnavailable("down")]))
    assert c3.source == "rules" and c3.sentences


def test_answers_with_text_or_bare_numbers_instead_of_ids_are_mapped_back():
    tr, beats = make(TEXT)
    first_text = beats.beats[0].text
    d = {"sentences": [{"beat": first_text[:30], "idea": "x", "importance": 1, "rel_to": "2"}, {"beat": "2", "idea": "y", "importance": 1}], "sections": [{"start_beat": "1", "end_beat": "B3"}]}
    out = C.repair_window(d, tr, beats.beats)
    assert out["sentences"][0]["beat"] == beats.beats[0].id and out["sentences"][1]["beat"] == "b2" and out["sentences"][0]["rel_to"] == "b2"
    assert out["sections"][0] == {"start_beat": "b1", "end_beat": "b3"}
    assert C.check_window(out, tr, beats.beats) == []


def test_a_name_said_once_and_not_confirmed_by_the_ai_is_dropped_but_a_repeated_one_stays():
    tr, beats = make("Today Ben Smith joined us. Amazon grows fast. Amazon hires. Zork was a game.")
    rules = C.rules_context(tr, beats, "en")
    assert rules.entity("Amazon") is not None
    reply = {"topic": "t", "summary": "s", "entities": [], "sentences": [], "sections": []}
    c = C.build(tr, beats, "en", provider=FakeProvider([reply]))
    assert c.source == "ai" and c.entity("Amazon") is not None and c.entity("Zork") is None


def test_the_owners_corrections_win_and_survive_a_rebuild():
    tr, beats = make(TEXT)
    ov = {"topic": "my own words", "entities": {"amazon": {"type": "place"}, "ebay": {"remove": True}}}
    c = C.build(tr, beats, "en", provider=FakeProvider([ai_reply(beats, tr)]), overrides=ov)
    assert c.topic == "my own words" and c.entity("Amazon").type == "place" and c.entity("Amazon").source == "owner" and c.entity("eBay") is None
    c2 = C.build(tr, beats, "en", use_ai=False, overrides=ov)                          # a rebuild without the AI keeps them too
    assert c2.entity("Amazon").type == "place" and c2.entity("eBay") is None


def test_long_videos_are_read_in_windows_that_carry_the_topic():
    text = " ".join(f"Sentence number {i} is about money and profit and the price of things." for i in range(1, 120))
    tr, beats = make(text, 0.3)
    prompts = []

    def fake(system, prompt, schema, images):
        prompts.append(prompt)
        ids = [ln.split(":")[0] for ln in prompt.splitlines() if ln.startswith("b") and ":" in ln]
        return {"topic": f"money window {len(prompts)}", "summary": "about money", "entities": [], "sentences": [{"beat": ids[0], "idea": "i", "importance": 1}], "sections": []}
    c = C.build(tr, beats, "en", provider=FakeProvider(fake))
    assert len(prompts) >= 2 and "What the whole video is about so far: money window 1" in prompts[1]
    assert c.source == "ai"


@pytest.fixture()
def client(ref):
    from fastapi.testclient import TestClient
    from vt.server.app import app

    with TestClient(app) as c:
        yield c


def test_the_api_reads_corrects_and_reports_when_the_reading_is_out_of_date(ref, client):
    assert client.get("/api/projects/reference/context").json()["context"] is None
    c = C.rules_context(ref.transcript(), ref.beats(), "bn")
    c.hash = C.current_hash(ref)
    c.entities.append(C.Entity(name="Zed", type="name", mentions=[ref.transcript().words[0].id]))
    C.save(ref, c)
    v = client.get("/api/projects/reference/context").json()
    assert v["stale"] is False and v["context"]["sentences"]
    assert client.put("/api/projects/reference/context/entity", json={"name": "Zed", "type": "bogus"}).status_code == 422
    assert client.put("/api/projects/reference/context/entity", json={"name": "Nobody", "type": "place"}).status_code == 404
    fixed = client.put("/api/projects/reference/context/entity", json={"name": "Zed", "type": "place"}).json()
    assert next(e for e in fixed["context"]["entities"] if e["name"] == "Zed")["type"] == "place" and fixed["overrides"]["entities"]["zed"]["type"] == "place"
    assert client.put("/api/projects/reference/context/topic", json={"topic": "  "}).status_code == 422
    assert client.put("/api/projects/reference/context/topic", json={"topic": "about my shop"}).json()["context"]["topic"] == "about my shop"
    client.put("/api/projects/reference/words/w1", json={"text": "changed"})                      # an edit of the words makes the reading out of date
    assert client.get("/api/projects/reference/context").json()["stale"] is True
    job = client.post("/api/projects/reference/context?ai=false").json()
    for _ in range(200):
        j = client.get(f"/api/jobs/{job['id']}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "done"
    again = client.get("/api/projects/reference/context").json()
    assert again["stale"] is False and again["context"]["topic"] == "about my shop"             # the owner's topic survived the rebuild
