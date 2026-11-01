"""Worked examples for the prompt. tests/test_script.py validates each one against its own beats, so they cannot go stale."""
from __future__ import annotations

from ..schema import Beat, Beats, Transcript, Word


def make(texts: list[str]) -> tuple[Transcript, Beats]:
    words, beats, t = [], [], 0.2
    for bi, text in enumerate(texts):
        ids, t0 = [], t
        for tok in text.split():
            w = Word(id=f"w{len(words) + 1}", text=tok, start=round(t, 2), end=round(t + 0.3, 2))
            words.append(w)
            ids.append(w.id)
            t += 0.35
        beats.append(Beat(id=f"b{bi + 1}", word_ids=ids, start=t0, end=round(t, 2), text=text))
    return Transcript(words=words), Beats(beats=beats)


ED_TEXTS = ["Hello everyone today we learn about gravity", "Gravity is the pull between masses", "Drop a ball and it falls", "Remember gravity never stops"]
STORY_TEXTS = ["Rafi found a lost wallet on the street", "He wondered what to do", "Then he ran to the shop to return it", "The owner was very happy"]
PRODUCT_TEXTS = ["Meet the new Notely app", "Write notes in seconds", "It costs only 5 dollars a month", "Download it today"]

ED = {
    "version": "1.0", "kind": "stick", "meta": {"language": "en", "audience": "students 12-15", "tone": "playful", "aspect": "9:16"},
    "cast": [{"id": "maya", "role": "teacher", "name": "Maya", "style": {"color": "#1f2937", "head": "round", "accessory": "glasses"}}],
    "sets": [{"id": "lab", "kind": "classroom", "props": ["ball"]}],
    "scenes": [
        {"id": "s1", "beats": ["b1"], "set": "lab", "camera": {"shot": "medium", "move": "push_in"}, "transition_in": "fade",
         "actions": [{"at_word": "w1", "who": "maya", "do": "walk_in", "from": "left", "to": 0.4}, {"at_word": "w2", "who": "maya", "do": "wave"}],
         "overlays": [{"type": "title", "text": "Gravity", "at_word": "w7"}]},
        {"id": "s2", "beats": ["b2"], "set": "lab", "camera": {"shot": "medium", "move": "none"}, "transition_in": "slide_left",
         "actions": [{"at_word": "w11", "who": "maya", "do": "point", "target": "board"}, {"at_word": "w12", "who": "maya", "do": "explain"}],
         "overlays": [{"type": "definition", "term": "Gravity", "meaning": "the pull between masses", "at_word": "w11"}]},
        {"id": "s3", "beats": ["b3"], "set": "lab", "camera": {"shot": "close", "move": "none"}, "transition_in": "cut",
         "actions": [{"at_word": "w14", "who": "maya", "do": "carry", "prop": "ball"}, {"at_word": "w18", "who": "maya", "do": "drop"}],
         "overlays": [{"type": "arrow", "direction": "down", "at_word": "w18"}]},
        {"id": "s4", "beats": ["b4"], "set": "lab", "camera": {"shot": "medium", "move": "pull_out"}, "transition_in": "fade",
         "actions": [{"at_word": "w20", "who": "maya", "do": "nod"}, {"at_word": "w22", "who": "maya", "do": "react", "emotion": "happy"}],
         "overlays": [{"type": "tag", "text": "Gravity never stops", "at_word": "w21"}], "sfx": [{"at_word": "w22", "id": "ding"}]},
    ],
}

STORY = {
    "version": "1.0", "kind": "stick", "meta": {"language": "en", "audience": "everyone", "tone": "warm", "aspect": "9:16"},
    "cast": [{"id": "rafi", "role": "friend", "name": "Rafi", "style": {"color": "#2563eb"}}, {"id": "owner", "role": "elder", "name": "Owner", "style": {"color": "#b45309"}}],
    "sets": [{"id": "road", "kind": "street", "props": ["wallet"]}, {"id": "bazaar", "kind": "market", "props": []}],
    "scenes": [
        {"id": "s1", "beats": ["b1"], "set": "road", "camera": {"shot": "wide", "move": "pan_right"}, "transition_in": "fade",
         "actions": [{"at_word": "w1", "who": "rafi", "do": "walk_in", "from": "left", "to": 0.4}, {"at_word": "w3", "who": "rafi", "do": "look_at", "target": "wallet"},
                     {"at_word": "w4", "who": "rafi", "do": "react", "emotion": "surprised"}], "overlays": []},
        {"id": "s2", "beats": ["b2"], "set": "road", "camera": {"shot": "close", "move": "none"}, "transition_in": "cut",
         "actions": [{"at_word": "w9", "who": "rafi", "do": "think"}], "overlays": [{"type": "question", "text": "What should he do?", "at_word": "w10"}]},
        {"id": "s3", "beats": ["b3"], "set": "bazaar", "camera": {"shot": "wide", "move": "follow"}, "transition_in": "slide_left",
         "actions": [{"at_word": "w16", "who": "rafi", "do": "walk_to", "to": 0.7}, {"at_word": "w18", "who": "owner", "do": "walk_in", "from": "right", "to": 0.8}], "overlays": []},
        {"id": "s4", "beats": ["b4"], "set": "bazaar", "camera": {"shot": "medium", "move": "push_in"}, "transition_in": "fade",
         "actions": [{"at_word": "w25", "who": "owner", "do": "celebrate"}, {"at_word": "w26", "who": "rafi", "do": "high_five", "target": "owner"}],
         "overlays": [], "sfx": [{"at_word": "w27", "id": "ding"}]},
    ],
}

PRODUCT = {
    "version": "1.0", "kind": "explainer", "meta": {"language": "en", "audience": "busy professionals", "tone": "confident", "aspect": "9:16"},
    "cast": [], "sets": [],
    "scenes": [
        {"id": "s1", "beats": ["b1"], "overlays": [{"type": "title", "text": "Notely", "at_word": "w4"}, {"type": "icon", "name": "lucide:notebook-pen", "label": "notes", "at_word": "w5"}],
         "layout": "stack", "transition_in": "fade"},
        {"id": "s2", "beats": ["b2"], "overlays": [{"type": "keyword", "text": "seconds", "icon": "lucide:timer", "style": "stamp", "at_word": "w9"}],
         "layout": "hero", "transition_in": "zoom"},
        {"id": "s3", "beats": ["b3"], "overlays": [{"type": "price_tag", "price": "$5", "label": "per month", "at_word": "w13"}], "layout": "hero", "transition_in": "slide_up"},
        {"id": "s4", "beats": ["b4"], "overlays": [{"type": "cta", "headline": "Download it today", "button": "Get Notely", "at_word": "w17"}], "layout": "hero", "transition_in": "fade"},
    ],
}

EXAMPLES_SCRIPTS = [
    ("an education clip (stick figures)", "\n".join(f"[{b.id}] " + " ".join(f"{w}:{make(ED_TEXTS)[0].by_id()[w].text}" for w in b.word_ids) for b in make(ED_TEXTS)[1].beats), ED),
    ("a story (two stick figures, two places)", "\n".join(f"[{b.id}] " + " ".join(f"{w}:{make(STORY_TEXTS)[0].by_id()[w].text}" for w in b.word_ids) for b in make(STORY_TEXTS)[1].beats), STORY),
    ("a product explainer (no characters, overlays only)", "\n".join(f"[{b.id}] " + " ".join(f"{w}:{make(PRODUCT_TEXTS)[0].by_id()[w].text}" for w in b.word_ids) for b in make(PRODUCT_TEXTS)[1].beats), PRODUCT),
]
ALL = [(ED_TEXTS, ED), (STORY_TEXTS, STORY), (PRODUCT_TEXTS, PRODUCT)]
