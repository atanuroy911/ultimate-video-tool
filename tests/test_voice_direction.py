"""Voice direction and vocal events: one vocabulary, each engine's own dialect, and captions that never show the notes."""
from vt import voice_direction as VD


def test_a_note_and_events_are_taken_out_of_the_words():
    d = VD.parse("{slowly, with a restrained, serious tone} I never told anyone (sigh) until today (laugh).")
    assert d.instruction == "slowly, with a restrained, serious tone"
    assert d.events == ["sigh", "laugh"]
    assert d.text == "I never told anyone until today."
    assert VD.strip("Well (clears throat) hello.") == "Well hello."


def test_ordinary_brackets_and_unknown_tags_stay_as_words():
    d = VD.parse("The price (about 20 dollars) is fine [see note] and (smile) too.")
    assert d.events == [] and "(about 20 dollars)" in d.text and "[see note]" in d.text and "(smile)" in d.text


def test_chinese_and_omnivoice_forms_are_understood():
    assert VD.parse("好的[笑]，我们开始[叹气]。").events == ["laugh", "sigh"]
    assert VD.parse("Ha [laughter] that was good [sigh]").events == ["laugh", "sigh"]
    assert VD.parse("(laughs) and (clear throat) and (coughing)").events == ["laugh", "clears throat", "cough"]


def test_breeze_takes_a_free_instruction_and_its_own_event_tags():
    r = VD.render(VD.parse("{whispering} I know (laugh) really."), "breeze")
    assert r.spoken == "I know (laugh) really." and r.instruction == "whispering" and r.dropped == []


def test_omnivoice_follows_only_whisper_and_two_events():
    d = VD.parse("{slowly and sadly} Well (sigh) then (cough).")
    r = VD.render(d, "omnivoice")
    assert r.spoken == "Well [sigh] then." and r.instruction == "" and r.rate == 0.9
    assert any("cough" in x for x in r.dropped) and any("only 'whisper'" in x for x in r.dropped)
    assert VD.render(VD.parse("{Whisper} Hush."), "omnivoice").instruction == "whisper"


def test_a_voice_without_direction_says_so_and_keeps_the_speed():
    r = VD.render(VD.parse("{quickly, out of breath} Run (breath) now."), "none")
    assert r.spoken == "Run now." and r.instruction == "" and r.rate == 1.1
    assert r.dropped, "the person is told what the engine could not do"
    off = VD.render(VD.parse("{slowly} Hi (laugh)."), "breeze", direction_on=False)
    assert off.spoken == "Hi." and off.instruction == "" and off.rate == 1.0


def test_synthesize_keeps_notes_out_of_captions_and_timings_and_passes_direction(monkeypatch, tmp_path):
    import numpy as np
    import soundfile as sf

    from vt import tts

    got = []

    def synth(engine, voice, text, rate, out, instruction="", **_):
        got.append((voice, text, round(rate, 2), instruction))
        sf.write(str(out), 0.1 * np.sin(np.linspace(0, 400, 24000)).astype("float32"), 24000)

    monkeypatch.setattr(tts, "synth_sentence", synth)
    monkeypatch.setattr(tts, "dialect_for", lambda *a, **k: "breeze")
    out = tts.synthesize("{softly} Hello there (sigh). Second sentence.", tmp_path / "o.wav", engine="comfyvoice", voice="me:x",
                         notes={1: {"instruction": "with a smile", "before": "laugh"}})
    assert got[0][1] == "Hello there (sigh)." and got[0][3] == "softly"
    assert got[1][1] == "(laugh) Second sentence." and got[1][3] == "with a smile"
    assert [s["text"] for s in out["sentences"]] == ["Hello there.", "Second sentence."]
    assert [w["text"] for s in out["sentences"] for w in s["words"]] == ["Hello", "there.", "Second", "sentence."]
    assert out["sentences"][0]["direction"]["events"] == ["sigh"] and out["sentences"][1]["direction"]["instruction"] == "with a smile"
    got.clear()
    tts.synthesize("{softly} Hello (sigh).", tmp_path / "p.wav", engine="comfyvoice", voice="me:x", direction=False)
    assert got[0][1] == "Hello." and got[0][3] == ""


def test_the_director_suggests_notes_and_never_more_events_than_one_in_six():
    from vt.ai import FakeProvider

    sents = [f"Sentence number {i}." for i in range(12)]
    p = FakeProvider([{"items": [{"i": 0, "instruction": "calm and sure", "before": "breath"}, {"i": 3, "after": "laugh"}, {"i": 5, "before": "sigh"}, {"i": 9, "instruction": "slowly"}]}])
    out = VD.suggest(sents, "en", provider=p)
    assert out[0]["instruction"] == "calm and sure" and out[9] == {"instruction": "slowly"}
    events = [k for n in out.values() for k in ("before", "after") if k in n]
    assert len(events) == 2 and len(sents) // 6 == 2, "two events for twelve sentences, the third was dropped"


def test_without_an_ai_only_punctuation_speaks_and_no_event_is_invented():
    from vt.ai import FakeProvider

    out = VD.suggest(["We did it!", "Well...", "Plain sentence."], "en", use_ai=False)
    assert out == {0: {"instruction": "energetic and emphatic"}, 1: {"instruction": "slow and thoughtful"}}
    bad = VD.suggest(["One."], "en", provider=FakeProvider([{"items": [{"i": 7, "instruction": "x"}]}, {"items": [{"i": 7, "instruction": "x"}]}]))
    assert bad == {}, "a note for a sentence that does not exist is refused and the rules' notes stand"


def test_the_director_only_offers_sounds_the_voice_can_make():
    from vt.ai import FakeProvider

    sents = [f"Sentence number {i}." for i in range(6)]
    p = FakeProvider([{"items": [{"i": 0, "before": "breath"}, {"i": 1, "after": "laugh"}, {"i": 2, "instruction": "softly", "before": "cough"}]}])
    out = VD.suggest(sents, "en", provider=p, events=("laugh", "sigh"))
    assert out == {1: {"after": "laugh"}, 2: {"instruction": "softly"}}, "a breath or a cough is dropped for a voice that cannot make it"
    assert "Sounds this voice can make: laugh, sigh" in p.calls[0]["prompt"]
    none = VD.suggest(sents, "en", provider=FakeProvider([{"items": [{"i": 0, "after": "sigh"}]}]), events=())
    assert none == {}
