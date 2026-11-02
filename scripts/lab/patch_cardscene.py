"""Round 2b: a text-only card scene in a video that has pictures holds the frame for its sentence (1.5 to 3 s), then the nearest picture
fades in under it and the card leaves (owner: "we forget when to stop that full screen artifact and go back to the scene")."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def sub(path, old, new):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:80])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


sub("vt/compose/composer.py", '''        scene_d = {"id": sc.id, "start": start, "end": end, "layout": sc.layout,
                   "transition_in": sc.transition_in, "tone": sc.tone, "elements": els}''', '''        scene_d = {"id": sc.id, "start": start, "end": end, "layout": sc.layout,
                   "transition_in": sc.transition_in, "tone": sc.tone, "elements": els}
        if sc.backdrop is None and els and all(e["type"] in CARD_TYPES for e in els) and not sc.stick:
            last = max(sc.elements, key=lambda e: words_by_id[e.at_word].start)
            last_at = max(e["at"] for e in els)
            out = min(last_at + HOLD_MAX, max(last_at + HOLD_MIN, sentence_end.get(last.at_word, last_at) + 0.2))
            if out < end - 0.8:
                scene_d["_card_out"] = round(out, 3)       # decided below, once it is known whether the video has pictures''')
sub("vt/compose/composer.py", '''    highlight = {wid for sc in sf.scenes for wid in sc.caption.highlight_words}''', '''    _hand_cards_back(scenes_out)
    highlight = {wid for sc in sf.scenes for wid in sc.caption.highlight_words}''')
sub("vt/compose/composer.py", '''HOLD_MIN, HOLD_MAX = 1.5, 3.0                      # pacing.dwell: the main thing for 1.5 to 3 s, then the picture behind it again
''', '''HOLD_MIN, HOLD_MAX = 1.5, 3.0                      # pacing.dwell: the main thing for 1.5 to 3 s, then the picture behind it again
# full-frame text cards: in a video with pictures they say their line and give the frame back to a picture
CARD_TYPES = {"title", "big_number", "value_card", "quote", "question", "cta", "definition", "keyword", "tag", "stat_row", "equation", "price_tag"}


def _hand_cards_back(scenes: list[dict]) -> None:
    """A card scene marked `_card_out` borrows the nearest picture (the one before it, else the one after), which fades in at that time
    while the card's parts leave. Only in a video that has pictures: a video made of cards keeps its cards."""
    pictured = [i for i, s in enumerate(scenes) if s.get("backdrop")]
    for i, s in enumerate(scenes):
        out = s.pop("_card_out", None)
        if out is None or not pictured:
            continue
        j = max((k for k in pictured if k < i), default=None)
        j = j if j is not None else min(k for k in pictured if k > i)
        bd = dict(scenes[j]["backdrop"])
        bd.pop("offset", None)                        # an A-roll's place in the recording belongs to its own scene
        bd["from"] = out
        s["backdrop"] = bd
        for e in s["elements"]:
            e["until"] = out
''')

sub("renderer/runtime/vt-media.js", '''    sceneEl.insertBefore(bd, sceneEl.firstChild);
    sceneEl.classList.add("has-backdrop", "ink-" + (s.ink || "light"));''', '''    sceneEl.insertBefore(bd, sceneEl.firstChild);
    sceneEl.classList.add("has-backdrop", "ink-" + (s.ink || "light"));
    if (typeof b.from === "number" && b.from > sc.start) {          // a card said its line: the picture comes back under it (composer _hand_cards_back)
      tl.set(bd, { opacity: 0 }, sc.start);
      tl.to(bd, { opacity: 1, duration: 0.45, ease: "power1.out" }, b.from);
    }''')
print("ok")
