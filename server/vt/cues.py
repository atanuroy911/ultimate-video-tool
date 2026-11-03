"""Sound cues for a composed video: which sound role plays when. Pure data; the mixer picks the actual clips.

Every cue has a tier so one composition serves every density setting:
  1 essential (transitions, big impacts)   2 normal (one sound per element)   3 rich (per-item ticks, risers, cuts)
"""
from __future__ import annotations

STAGGER = 0.12   # seconds between items of a multi-item element (icons, list rows, equation parts, bars)

# element type -> (role of the first/only sound, tier, role of each following item or None, items key or count field)
ELEMENT_CUES: dict[str, dict] = {
    "title":      {"role": "pop", "tier": 2},
    "value_card": {"role": "chime", "tier": 2},
    "big_number": {"role": "impact", "tier": 1, "riser": True},
    "arrow":      {"role": "whoosh", "tier": 2},
    "icon_row":   {"role": "pop", "tier": 2, "items": "count", "item_role": "pop"},
    "tag":        {"role": "click", "tier": 2},
    "compare":    {"role": "whoosh", "tier": 2, "extra": [("pop", 0.24)]},
    "list":       {"role": "click", "tier": 2, "items": "items", "item_role": "click", "gap": 0.2},
    "equation":   {"role": "click", "tier": 2, "items": "parts", "item_role": "click", "gap": 0.2},
    "quote":      {"role": "chime", "tier": 2},
    "bar_chart":  {"role": "click", "tier": 2, "items": "bars", "item_role": "click", "gap": 0.16},
    "icon":       {"role": "pop", "tier": 2},
    "keyword":    {"role": "impact", "tier": 2, "extra": [("pop", 0.0)]},
    "sticker":    {"role": "pop", "tier": 2},
    "ring":       {"role": "chime", "tier": 2, "extra": [("click", 0.9)]},
    "line_chart": {"role": "whoosh", "tier": 2, "items": "points", "item_role": "click", "gap": 0.45},
    "steps":      {"role": "click", "tier": 2, "items": "items", "item_role": "click", "gap": 0.4},
    "timeline":   {"role": "whoosh", "tier": 2, "items": "events", "item_role": "click", "gap": 0.45},
    "definition": {"role": "chime", "tier": 2},
    "checklist":  {"role": "click", "tier": 2, "items": "items", "item_role": "chime", "gap": 0.5},
    "pros_cons":  {"role": "whoosh", "tier": 2, "extra": [("click", 0.8)]},
    "stat_row":   {"role": "impact", "tier": 2, "items": "stats", "item_role": "pop", "gap": 0.21},
    "question":   {"role": "chime", "tier": 2, "extra": [("click", 1.6)]},
    "feature_grid": {"role": "pop", "tier": 2, "items": "items", "item_role": "pop", "gap": 0.23},
    "cta":        {"role": "impact", "tier": 1, "extra": [("chime", 0.35)]},
    "price_tag":  {"role": "impact", "tier": 2, "extra": [("click", 0.5)]},
    "device":     {"role": "whoosh", "tier": 2, "items": "callouts", "item_role": "pop", "gap": 0.5},
    "speaker_card": {"role": "pop", "tier": 2},
    "cartoon":    {"role": "pop", "tier": 2, "extra": [("pop", 0.6)]},
    "media_frame": {"role": "whoosh", "tier": 2},
    "flow":       {"role": "click", "tier": 2, "items": "nodes", "item_role": "click", "gap": 0.45},
    "cycle":      {"role": "whoosh", "tier": 2, "items": "items", "item_role": "pop", "gap": 0.4},
    "hierarchy":  {"role": "pop", "tier": 2, "items": "branches", "item_role": "click", "gap": 0.5},
    "venn":       {"role": "whoosh", "tier": 2, "extra": [("chime", 0.9)]},
    "funnel":     {"role": "whoosh", "tier": 2, "items": "stages", "item_role": "click", "gap": 0.5},
    "pyramid":    {"role": "pop", "tier": 2, "items": "levels", "item_role": "click", "gap": 0.45},
    "matrix":     {"role": "pop", "tier": 2, "extra": [("click", 1.2)]},
    "pictogram":  {"role": "pop", "tier": 2, "extra": [("chime", 1.3)]},
    "gauge":      {"role": "whoosh", "tier": 2, "extra": [("chime", 1.0)]},
}
SFX_ROLE = {"pop": "pop", "ding": "chime", "whoosh": "whoosh", "click": "click"}      # Video Script sound ids -> mixer roles
STICK_CUES = {"jump": ("impact", 0.7, 2), "fall": ("impact", 0.35, 1), "celebrate": ("chime", 0.0, 2), "high_five": ("click", 0.5, 2), "handshake": ("click", 0.5, 3),
              "hold_sign": ("pop", 0.0, 2), "write_board": ("click", 0.0, 3), "drop": ("click", 0.6, 3), "carry": ("click", 0.6, 3)}
TRANSITION_CUES: dict[str, list[tuple[str, int]]] = {
    "cut": [("click", 3)],
    "fade": [],
    "slide_up": [("whoosh", 1)],
    "slide_left": [("whoosh", 1)],
    "zoom": [("subdrop", 1)],
    "wipe": [("whoosh", 1)],
    "whip": [("whoosh", 1)],
}


def build_cues(scenes: list[dict]) -> list[dict]:
    """scenes: resolved scenes (start, transition_in, elements with 'at'). Returns time-ordered cues, thinned."""
    cues: list[dict] = []
    for i, sc in enumerate(scenes):
        if i > 0:
            for role, tier in TRANSITION_CUES.get(sc["transition_in"], []):
                cues.append({"t": sc["start"], "role": role, "tier": tier})
        for c in sc.get("sfx") or []:                                   # sounds written into the Video Script
            cues.append({"t": c["t"], "role": SFX_ROLE.get(c["id"], "pop"), "tier": 1})
        for a in (sc.get("stick") or {}).get("actions", []):             # stick-figure actions with a physical moment
            spec = STICK_CUES.get(a["do"])
            if spec:
                cues.append({"t": round(a["start"] + spec[1], 3), "role": spec[0], "tier": spec[2]})
        for el in sc["elements"]:
            spec = ELEMENT_CUES.get(el["type"])
            if not spec:
                continue
            t = el["at"]
            if spec.get("riser") and t > 1.6:
                cues.append({"t": round(t - 1.4, 3), "role": "riser", "tier": 3})
            cues.append({"t": t, "role": spec["role"], "tier": spec["tier"]})
            for role, dt in spec.get("extra", []):
                cues.append({"t": round(t + dt, 3), "role": role, "tier": 3})
            key = spec.get("items")
            if key:
                n = el.get(key) if key == "count" else len(el.get(key) or [])
                gap = spec.get("gap", STAGGER)
                for k in range(1, int(n or 0)):
                    cues.append({"t": round(t + k * gap, 3), "role": spec["item_role"], "tier": 3})
    cues.sort(key=lambda c: (c["t"], c["tier"]))
    out: list[dict] = []
    for c in cues:                                    # no two sounds of one role within 90 ms; at most ~4 per second overall
        if any(o["role"] == c["role"] and c["t"] - o["t"] < 0.09 for o in out[-6:]):
            continue
        if sum(1 for o in out[-8:] if c["t"] - o["t"] < 1.0) >= 4 and c["tier"] > 1:
            continue
        out.append(c)
    return out
