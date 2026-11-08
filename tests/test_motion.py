"""Motion graphics (vt/compose/motion.py + renderer/runtime/vt-motion.js): every shotcraft card is realised, choices are varied and stable."""
import json
import re

from vt import paths
from vt.compose import motion as MO


def _registry():
    js = (paths.RUNTIME / "vt-motion.js").read_text(encoding="utf-8")
    out = {}
    for reg, letter in (("text", "T"), ("trans", "R"), ("scene", "S")):
        out[reg] = set(re.findall(rf'\b{letter}\["([a-z0-9-]+)"\]\s*=', js))
    return out


def test_every_one_of_the_124_cards_is_mapped_to_a_recipe_that_exists():
    cards = json.loads((paths.ROOT.parent / "third_party" / "video-shotcraft" / "index.json").read_text(encoding="utf-8"))["cards"]
    reg = _registry()
    names = {c["name"] for c in cards}
    assert len(names) == 124 and names <= set(MO.CARDS), sorted(names - set(MO.CARDS))
    missing = [(k, r, f) for k, (r, f) in MO.CARDS.items() if f not in reg[r]]
    assert not missing, missing
    used = set().union(*MO.POOLS.values(), MO.TRANSITIONS, MO.OPENINGS, MO.COVERING_OPENINGS, MO.OUTROS, MO.CAMERA, MO.RHYTHM)
    assert used <= reg["text"] | reg["trans"] | reg["scene"]


def _comp(n=12):
    sc = []
    for i in range(n):
        sc.append({"id": f"s{i + 1}", "start": i * 3.0, "end": i * 3.0 + 3, "elements": [{"type": "keyword", "text": "money" if i % 3 else "10 dollars"},
                                                                                         {"type": "sticker", "label": "coin"}, {"type": "tag", "text": "Why?"}]})
    return {"scenes": sc}


def test_choices_fit_the_content_vary_and_are_stable():
    d = MO.apply(_comp(), "auto", seed="p1")
    s = d["scenes"]
    assert s[0]["elements"][0]["fx"] == "countdown-arc-scatter"                       # "10 dollars": the number counts up
    assert s[1]["elements"][2]["fx"] in MO.POOLS["question"]                           # "Why?"
    fx = [e["fx"] for x in s for e in x["elements"]]
    assert all(a != b for a, b in zip(fx, fx[1:]) if a not in MO.POOLS["number"])     # never the same entrance twice in a row
    tx = [x.get("tx") for x in s[1:]]
    assert all(a != b for a, b in zip(tx, tx[1:]) if a and b) and sum(t is None for t in tx) >= 1
    assert s[0]["moves"][0] in MO.OPENINGS and s[-1]["moves"][0] in MO.OUTROS
    assert MO.apply(_comp(), "auto", seed="p1") == d                                    # deterministic
    assert "fx" not in json.dumps(MO.apply(_comp(), "off", seed="p1"))


def test_an_automatic_opening_leaves_the_first_frame_whole():
    # the owner's cartoon (2026-11-08): `fracture` hid the first 0.2 s behind bars of the ink colour
    for seed in ("a", "b", "c", "vt", "maya", "x1", "x2", "x3"):
        s = MO.apply({"scenes": [{"id": "s1", "start": 0, "end": 3, "elements": []}, {"id": "s2", "start": 3, "end": 6, "elements": []}]}, seed=seed)["scenes"]
        assert s[0]["moves"][0] in MO.OPENINGS and s[0]["moves"][0] not in MO.COVERING_OPENINGS
    asked = MO.apply({"scenes": [{"id": "s1", "start": 0, "end": 3, "camera_move": "fracture", "elements": []}]})["scenes"]
    assert asked[0]["moves"] == ["fracture"]                         # asked for by name: kept
