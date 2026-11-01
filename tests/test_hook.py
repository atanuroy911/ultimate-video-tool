"""Hook proposals (R8): they only trim or move the author's own words, and an AI line is kept only when it adds no fact."""
from vt.reel import hook as H

WEAK = ("Hi everyone, welcome back to my channel, today I want to talk about something. So, a lot of people forget to drink water when they work. "
        "The result is headaches and tiredness by the afternoon. Even mild dehydration can slow your thinking by 20 percent. Keep a bottle on your desk.")
STRONG = "Why do you always feel tired at three? Because you forgot water. Keep a bottle on your desk."


def test_a_greeting_opening_is_weak_and_a_question_is_not():
    assert H.is_weak(WEAK) and not H.is_weak(STRONG)
    assert H.propose(STRONG) == [], "nothing is proposed for a strong opening"


def test_the_rules_trim_the_greeting_and_lead_with_the_strongest_line():
    got = {p["id"]: p for p in H.propose(WEAK)}
    assert got["cut-greeting"]["script"].startswith("So, a lot of people") or got["cut-greeting"]["script"].startswith("a lot of people")
    assert "welcome back" not in got["cut-greeting"]["script"]
    lead = got["lead-with-strongest"]["script"]
    assert lead.startswith("Even mild dehydration can slow your thinking by 20 percent.")
    words = lambda s: sorted(s.replace(",", "").replace(".", "").lower().split())
    assert words(lead) == words(" ".join(H.sentences(WEAK)[1:])), "moved, never rewritten: the same words in a new order"


def test_an_ai_line_with_an_invented_fact_is_dropped():
    good = "Do you forget to drink water when you work?"
    bad = "Drinking 3 litres of water cures every headache."
    got = H.propose(WEAK, ai_rewrites=[bad, good])
    assert len(got) == 2
    texts = " ".join(p["script"] for p in got)
    assert "cures every headache" not in texts
    assert H.grounded(good, WEAK) and not H.grounded(bad, WEAK)


def test_the_module_and_the_routes(ref):
    import json

    from fastapi.testclient import TestClient

    from vt.modules.executor import Executor
    from vt.server.app import app

    ref.script_path.write_text(json.dumps({"text": WEAK, "engine": "kokoro", "voice": "af_heart"}), encoding="utf-8")
    r = Executor(ref.dir).call("direct.improve_hook", {"use_ai": False})
    assert r.ok and r.output["weak"] and 1 <= len(r.output["proposals"]) <= 2
    with TestClient(app) as c:
        d = c.get("/api/projects/reference/hook?ai=false").json()
        assert d["weak"] and d["first"].startswith("Hi everyone")
        assert c.get("/api/projects/nope/hook").status_code == 404
