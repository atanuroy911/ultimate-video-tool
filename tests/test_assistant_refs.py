"""W13.2: the Director chat writes references exactly as the Claude Code tab does (shared fixture with client/desktop/test-acp-agents.js)."""
import json
from pathlib import Path

from vt.assistant_refs import clean, with_refs

CASES = json.loads((Path(__file__).parent / "fixtures" / "refs.json").read_text(encoding="utf-8"))


def test_same_text_as_the_desktop_formatter():
    for case in CASES:
        assert with_refs(case["text"], case["refs"]) == case["expected"]


def test_bad_references_are_dropped():
    assert clean([{"kind": "evil"}, "x", {"kind": "time", "t": float("nan")}, {"kind": "scene", "scene": "s1" * 100}]) == [{"kind": "time"}, {"kind": "scene", "scene": ("s1" * 100)[:64]}]
    assert len(clean([{"kind": "time", "t": 1}] * 20)) == 8
