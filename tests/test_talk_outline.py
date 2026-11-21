"""C10 look-ahead: a long talk is read in overlapping chunks with a running summary; the AI marks examples, code only splits, clips and merges."""
from vt import talk_outline as T


def _words(n_sentences: int, words_each: int = 6) -> list[dict]:
    out, t = [], 0.0
    for s in range(n_sentences):
        for i in range(words_each):
            text = f"w{s}_{i}" + ("." if i == words_each - 1 else "")
            out.append({"text": text, "start": t, "end": t + 0.3})
            t += 0.35
    return out


def test_sentences_end_on_punctuation_pauses_and_length():
    words = [{"text": "Hello", "start": 0, "end": 0.3}, {"text": "there.", "start": 0.4, "end": 0.7},
             {"text": "Long", "start": 0.8, "end": 1.0}, {"text": "pause", "start": 3.0, "end": 3.2}]
    s = T.sentences(words)
    assert [x["text"] for x in s] == ["Hello there.", "Long", "pause"]
    assert s[1]["start"] == 0.8 and s[2]["n"] == 3
    many = [{"text": "a", "start": i * 0.1, "end": i * 0.1 + 0.05} for i in range(90)]
    assert max(len(x["text"].split()) for x in T.sentences(many)) <= 40


def test_chunks_overlap_carry_the_summary_and_merge_an_example_seen_twice():
    words = _words(130)
    calls = []

    def ask(system, prompt):
        calls.append(prompt)
        rng = prompt.split("Here are sentences ")[1].split(":")[0]
        first, last = (int(x) for x in rng.split(" to "))
        ans = {"summary": f"summary up to {last}", "sections": [{"first": first, "last": last, "point": "a part"}],
               "examples": [], "keep_on_speaker": []}
        if first <= 55 <= last:           # an example across the first chunk edge (sentences 50 to 58), seen by two chunks
            ans["examples"].append({"first": 50, "last": min(58, last), "kind": "case", "about": "the beetle case", "show": "a beetle"})
        if first == 1:
            ans["keep_on_speaker"].append({"first": 1, "last": 3, "why": "opening"})
            ans["examples"].append({"first": 999, "last": 1000, "kind": "numbers", "about": "out of range", "show": "x"})
        return ans

    out = T.outline(words, ask=ask)
    assert len(calls) == 3 and "summary up to 60" in calls[1]             # 60 + 52 + 52 sentences, each later chunk sees the summary before it
    assert [e["first"] for e in out["examples"]] == [50] and out["examples"][0]["last"] == 58
    assert out["examples"][0]["start"] == out["sentences"][49]["start"]
    assert out["keep_on_speaker"][0]["why"] == "opening"
    assert all(s["first"] <= s["last"] for s in out["sections"])
    assert out["summary"] == "summary up to 130"


def test_merge_keeps_the_longer_description():
    got = T.merge_examples([{"first": 5, "last": 8, "kind": "case", "about": "short", "show": "a"},
                            {"first": 6, "last": 12, "kind": "story", "about": "long", "show": "b"},
                            {"first": 20, "last": 22, "kind": "list", "about": "other", "show": "c"}])
    assert [(e["first"], e["last"], e["about"]) for e in got] == [(5, 12, "long"), (20, 22, "other")]


def test_speech_recognition_asks_the_local_engines_to_free_the_card(monkeypatch):
    """ComfyUI and Ollama on this computer are asked to let go of the card before the speech model loads there (ISSUES 2026-11-22)."""
    import httpx

    from vt import llm
    from vt.server import comfy_routes
    from vt.stages import asr

    posted = []
    monkeypatch.setattr(comfy_routes, "comfy_url", lambda: "http://127.0.0.1:8188")
    monkeypatch.setattr(httpx, "post", lambda url, **kw: posted.append(url))
    monkeypatch.setattr(llm, "release", lambda url=None: ["gemma4:e2b"])
    monkeypatch.setattr(llm, "settings", lambda: {"ollama_url": "http://127.0.0.1:11434"})
    assert asr.free_card() == ["comfyui", "ollama"] and posted == ["http://127.0.0.1:8188/free"]
    monkeypatch.setattr(comfy_routes, "comfy_url", lambda: "http://10.0.0.5:8188")       # another computer's engine is left alone
    posted.clear()
    assert asr.free_card() == ["ollama"] and posted == []


def test_touching_examples_stay_two_and_a_too_long_example_is_sent_back():
    got = T.merge_examples([{"first": 10, "last": 20, "kind": "case", "about": "a", "show": "a"},
                            {"first": 19, "last": 30, "kind": "list", "about": "b", "show": "b"}])
    assert [(e["first"], e["last"]) for e in got] == [(10, 20), (21, 30)]
    errs = T.problems({"examples": [{"first": 60, "last": 112}, {"first": 5, "last": 6}]}, 53, 112)
    assert any("53 sentences" in e for e in errs) and any("between 53 and 112" in e for e in errs)


def test_look_ahead_names_each_example_by_its_beats():
    class B:
        def __init__(self, id, start, end): self.id, self.start, self.end = id, start, end

    beats = [B("b1", 0, 5), B("b2", 5, 10), B("b3", 10, 15), B("b4", 15, 20)]
    outline = {"summary": "A talk.", "examples": [{"start": 5.0, "end": 14.9, "kind": "analogy", "about": "a warehouse", "show": "robots between shelves"}],
               "keep_on_speaker": [{"start": 0, "end": 4.9, "why": "opening"}]}
    text = T.look_ahead_text(outline, beats)
    assert "E1 beats b2..b3 (5.0-14.9s) analogy: a warehouse | show: robots between shelves" in text
    assert "beats b1..b1 (opening)" in text and "aroll" in text
    assert T.look_ahead_text(None, beats) == "" and T.look_ahead_text({"examples": []}, beats) == ""


def test_captions_also_as_webvtt():
    from vt.compose.composer import to_srt, to_vtt

    chunks = [{"start": 1.5, "end": 3.25, "words": [{"text": "Hello"}, {"text": "there"}]}, {"start": 3661.0, "end": 3662.0, "words": [{"text": "Bye"}]}]
    assert to_vtt(chunks) == "WEBVTT\n\n00:00:01.500 --> 00:00:03.250\nHello there\n\n01:01:01.000 --> 01:01:02.000\nBye\n"
    assert "00:00:01,500 --> 00:00:03,250" in to_srt(chunks)
