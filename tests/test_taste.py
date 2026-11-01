"""The creator's taste (vt/taste.py): spellings, choices and notes learned from what the person changes."""
from vt import paths, taste
from vt.util import read_json


def test_a_spelling_fixed_in_two_videos_is_learned_for_all():
    assert not taste.learn_fix("ইল্ড", "ইয়েল্ড", "p1")
    assert not taste.learn_fix("ইল্ড", "ইয়েল্ড", "p1")                     # the same video twice is still one video
    assert taste.learn_fix("ইল্ড", "ইয়েল্ড", "p2")
    assert read_json(paths.GLOBAL_GLOSSARY)["ইল্ড"] == "ইয়েল্ড"
    assert not taste.learn_fix("a", "b", "p3") and not taste.learn_fix("same", "same", "p3")


def test_the_same_choice_twice_in_a_row_becomes_a_preference():
    assert taste.learn_choice("theme", "paper") is None
    assert taste.learn_choice("theme", "neon") is None
    assert taste.learn_choice("theme", "neon") == "neon"


def test_notes_become_a_hint_for_the_next_director():
    assert taste.director_hint() == ""
    for t in ["Make it funnier", "make it funnier", "Less talking"]:
        taste.learn_note(t)
    h = taste.director_hint()
    assert "make it funnier" in h.lower() and "less talking" in h.lower()


def test_word_fix_and_theme_choice_through_the_api(ref, monkeypatch):
    from fastapi.testclient import TestClient

    import vt.server.app as A
    from vt.project import Project

    p = Project("reference")
    heard = read_json(p.raw_transcript_path)["words"][0]["text"]
    with TestClient(A.app) as c:
        assert c.put("/api/projects/reference/words/w1", json={"text": heard + "X"}).status_code == 200
        assert read_json(taste._path())["fixes"] == {f"{heard}\t{heard}X": ["reference"]}
        themes = [t["name"] for t in c.get("/api/themes").json() if not t["name"].startswith("auto-")]
        c.patch("/api/projects/reference", json={"theme": themes[1]})
        c.patch("/api/projects/reference", json={"theme": themes[1]})
        assert c.get("/api/settings").json()["default_theme"] == themes[1]
