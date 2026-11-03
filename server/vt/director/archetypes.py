"""Scene archetypes: how a group of sentences can be shown. Each archetype has
  fit(group, ctx)   -> 0..1, how well the sentences suit it (0 = impossible, e.g. a chart needs numbers)
  build(group, ctx) -> list of element dicts (+ optional scene fields), or None when the data turns out not to be enough
The selector (plan.py) multiplies fit by the profile's weight and by variety rules. Builders only use what was actually said."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..planner.rules import SYMBOLS, _keyword, _visual_elements, localize_digits
from ..schema import Word
from ..stages.words import norm_token
from . import roles as R

BN_DIG = R.BN_DIG
TRIM = " ,.।?!;:،\"'“”‘’"


# ------------------------------------------------------------------ context + group
@dataclass
class Group:
    facts: list[R.Facts]
    media_id: Optional[str] = None
    media_kind: str = "image"
    media_ratio: float = 1.0                  # width / height of the assigned media

    @property
    def words(self) -> list[Word]:
        return [w for f in self.facts for w in f.words]

    @property
    def beats(self) -> list[str]:
        return [f.beat.id for f in self.facts]

    @property
    def start(self) -> float:
        return self.facts[0].beat.start

    @property
    def end(self) -> float:
        return self.facts[-1].beat.end

    @property
    def dur(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        return " ".join(f.text for f in self.facts)

    @property
    def numbers(self) -> list[dict]:
        return [n for f in self.facts for n in f.numbers]

    @property
    def years(self) -> list[tuple[str, Word]]:
        return [y for f in self.facts for y in f.years]

    @property
    def roles(self) -> set[str]:
        return set().union(*(f.roles for f in self.facts)) if self.facts else set()

    @property
    def role(self) -> str:
        return self.facts[0].role if len(self.facts) == 1 else next((f.role for f in self.facts if f.role != "claim"), "claim")

    def first_word(self) -> Word:
        return self.facts[0].words[0]


@dataclass
class Ctx:
    words: dict[str, Word]
    language: str
    picks: dict = field(default_factory=dict)
    profile: dict = field(default_factory=dict)
    usecase: str = "general"
    brief: dict = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(0))
    pattern: int = 0
    last_set: str = "plain"
    cast: dict[str, dict] = field(default_factory=dict)      # name/who -> consistent look across scenes
    names: list[str] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    media: dict = field(default_factory=dict)            # media id -> MediaItem (faces decide where text goes)
    aspect: str = "9:16"


def clip(s: str, n: int) -> str:
    s = s.strip(TRIM + " ")
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut or s[:n]).strip(TRIM + " ")


def _num_val(n: dict) -> float:
    return float(n.get("val") or 0)


def _fmt(disp: str) -> str:
    """10000 -> 10,000 (also with Bangla digits); years, decimals, symbols and short numbers are left alone."""
    m = re.fullmatch(r"([^\d০-৯]*)([\d০-৯]{5,})", disp)
    if not m:
        return disp
    digits = m.group(2)
    out = ""
    for k, ch in enumerate(reversed(digits)):
        if k and k % 3 == 0:
            out = "," + out
        out = ch + out
    return m.group(1) + out


def _label(n: dict, k: int = 20) -> str:
    return clip(n.get("label", ""), k)


# ------------------------------------------------------------------ builders
def b_title_card(g: Group, c: Ctx):
    topic = (c.brief or {}).get("topic") or ""
    if len(topic.split()) > 5 or re.match(r"(?i)\s*(the|this) (video|clip|text)\b|\s*about\b", topic):
        topic = ""                                                   # "The video describes a small power bank" is a note about the video, not a title
    kw = _keyword(g.words, _topics(c))
    from .phrases import tidy

    hook = tidy(g.facts[0].text, 40, min_content=2, whole=True)       # "Tired of slow video editing?" says more than "video"
    text = clip(topic, 40) if topic and g.facts[0].first else (hook or (_cap(clip(kw.text, 30)) if kw else clip(g.facts[0].text, 40)))
    els = [{"type": "title", "text": text, "at_word": g.first_word().id}]
    pk = c.picks.get(g.facts[0].beat.id)
    if pk and pk.sticker and pk.kind == "sticker":
        els.append({"type": "sticker", "emoji": pk.sticker, "label": "", "at_word": pk.word_id})
    return els, {}


def b_hero_number(g: Group, c: Ctx):
    nums = g.numbers
    if not nums:
        return None
    n = nums[0]
    els: list[dict] = []
    if n["kind"] == "percent":
        els.append({"type": "big_number", "value": n["disp"].rstrip("%")[:12], "unit": "%", "label": _label(n, 40), "at_word": n["word"].id})
    else:
        els.append({"type": "value_card", "value": n["disp"][:14], "label": _label(n, 36), "at_word": n["word"].id})
    if len(nums) >= 2 and nums[1]["kind"] == n["kind"] and nums[1]["word"].id != n["word"].id:
        els += [{"type": "arrow", "direction": "down", "at_word": nums[1]["word"].id}, {"type": "tag", "text": nums[1]["disp"][:28], "at_word": nums[1]["word"].id}]
    else:
        pk = next((c.picks[f.beat.id] for f in g.facts if f.beat.id in c.picks and c.picks[f.beat.id].sticker), None)
        if pk and pk.word_id != n["word"].id:
            els.append({"type": "sticker", "emoji": pk.sticker, "at_word": pk.word_id})
    return els, {"highlight": n["word"].id}


def b_ring(g: Group, c: Ctx):
    pcts = [n for n in g.numbers if n["kind"] == "percent"]
    if not pcts:
        return None
    n = pcts[0]
    raw = re.sub(r"[^\d.]", "", n["disp"].translate(BN_DIG))
    try:
        v = float(raw)
    except ValueError:
        return None
    if not 0 <= v <= 100:
        return None
    return [{"type": "ring", "value": v, "label": _label(n, 30), "display": n["disp"][:10], "at_word": n["word"].id}], {"highlight": n["word"].id}


def b_stat_row(g: Group, c: Ctx):
    nums = [n for n in g.numbers][:4]
    if len(nums) < 2:
        return None
    return [{"type": "stat_row", "stats": [{"value": _fmt(n["disp"])[:10], "label": _label(n, 20)} for n in nums], "at_word": nums[0]["word"].id}], {"highlight": nums[0]["word"].id}


def b_bar_compare(g: Group, c: Ctx):
    nums = [n for n in g.numbers if _num_val(n) > 0 or n["kind"] == "percent"][:5]
    if len(nums) < 2:
        return None
    if len(nums) == 2 and any(norm_token(w.text) in {"vs", "versus", "বনাম", "চেয়ে", "তুলনায়"} for w in g.words):
        a, b = nums
        return [{"type": "compare", "left": {"title": _label(a, 20), "value": a["disp"][:12]}, "right": {"title": _label(b, 20), "value": b["disp"][:12]}, "at_word": a["word"].id}], {}
    bars = []
    for n in nums:
        v = _num_val(n)
        if n["kind"] == "percent":
            v = float(re.sub(r"[^\d.]", "", n["disp"].translate(BN_DIG)) or 0)
        bars.append({"label": _label(n, 16) or "·", "value": max(v, 0.0), "display": n["disp"][:12]})
    return [{"type": "bar_chart", "bars": bars, "at_word": nums[0]["word"].id}], {}


def b_line_trend(g: Group, c: Ctx):
    nums = [n for n in g.numbers][:8]
    if len(nums) < 3:
        return None
    unit = "%" if all(n["kind"] == "percent" for n in nums) else ""
    pts = []
    years = [y for y, _ in g.years]
    for i, n in enumerate(nums):
        v = float(re.sub(r"[^\d.\-]", "", n["disp"].translate(BN_DIG)) or _num_val(n) or 0)
        pts.append({"label": (years[i] if i < len(years) else _label(n, 10) or str(i + 1))[:10], "value": v})
    return [{"type": "line_chart", "points": pts, "unit": unit, "label": "", "at_word": nums[0]["word"].id}], {}


def b_timeline(g: Group, c: Ctx):
    ys = g.years[:5]
    if len(ys) < 2:
        return None
    evs = []
    ws = g.words
    for disp, w in ys:
        i = next((k for k, x in enumerate(ws) if x.id == w.id), 0)
        rest = [x.text for x in ws[i + 1:i + 6] if norm_token(x.text) not in R.DETERMINERS][:4]
        evs.append({"when": disp[:12], "what": clip(" ".join(rest) or disp, 32)})
    return [{"type": "timeline", "events": evs, "at_word": ys[0][1].id}], {}


def _step_title(text: str, lang: str) -> tuple[str, str]:
    """'First, paste your script' -> ('paste your script', ''); long sentences split into a title that fits and the rest as detail."""
    toks = [t for t in text.split() if norm_token(t) not in R.STEP_WORDS and norm_token(t) not in {"to", "the", "a", "an"}]
    title, i = "", 0
    while i < len(toks) and len((title + " " + toks[i]).strip()) <= 24:
        title = (title + " " + toks[i]).strip()
        i += 1
    return clip(title or " ".join(toks[:2]), 24), clip(" ".join(toks[i:]), 44)


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:] if t and not R.BN.search(t[:1]) else t


def b_steps(g: Group, c: Ctx):
    from .phrases import tidy, tidy_all

    steps = [f for f in g.facts if "step" in f.roles and (_has_ordinal(f) or len([x for x in g.facts if "step" in x.roles]) >= 3)]
    items = []
    if len(steps) >= 2:
        for f in steps[:5]:
            t, d = _step_title(f.text, c.language)
            t2 = tidy(t, 24)
            if not t2:
                return None                                    # one broken step spoils the whole list
            items.append({"title": _cap(t2), "detail": tidy(d, 44) or ""})
        at = steps[0].words[0].id
    else:
        lst = next((f for f in g.facts if len(f.items) >= 3), None)
        if not lst:
            return None
        titles = tidy_all([t for t, _ in lst.items[:5]], 24, need=3)
        if not titles:
            return None
        items = [{"title": _cap(t), "detail": ""} for t in titles]
        at = lst.items[0][1].id
    if len(items) < 2:
        return None
    return [{"type": "steps", "items": items[:5], "at_word": at}], {}


ORDINALS = {"first", "second", "third", "fourth", "fifth", "firstly", "secondly", "thirdly", "finally", "lastly", "step", "next",
            "প্রথমে", "প্রথমত", "দ্বিতীয়ত", "তৃতীয়ত", "অবশেষে", "সবশেষে", "ধাপ"}


def _has_ordinal(f) -> bool:
    """'First, ...' / 'Step 2 ...' / 'Finally ...' near the start: a real step, not any sentence that happens to contain 'then'."""
    return any(norm_token(w.text) in ORDINALS for w in f.words[:3])


def b_checklist(g: Group, c: Ctx):
    from .phrases import tidy_all

    lst = next((f for f in g.facts if len(f.items) >= 3), None)
    if not lst:
        return None
    items = tidy_all([t for t, _ in lst.items[:5]], 36, need=3)
    if not items:
        return None
    return [{"type": "checklist", "items": [_cap(t) for t in items], "title": "", "at_word": lst.items[0][1].id}], {}


def b_definition(g: Group, c: Ctx):
    from ..visuals import terms as T
    from .phrases import tidy

    f = next((x for x in g.facts if x.definition), None)
    if not f:
        return None
    term, meaning, w = f.definition
    term2, meaning2 = tidy(term, 28), tidy(meaning, 90, min_content=2)
    if not term2 or not meaning2 or "," in term or len(meaning2.split()) < 3 or len(f.items) >= 3:     # "Rent, food and fuel are all affected" is a list
        return None
    if not R.BN.search(term2) and not any(T.is_key_term(x, _topics(c)) for x in term2.split()):
        return None                                            # "it", "this one" is not a term to define
    return [{"type": "definition", "term": _cap(term2), "meaning": meaning2, "at_word": w.id}], {"highlight": w.id}


QUESTION_START = {"what", "why", "how", "who", "when", "where", "which", "is", "are", "do", "does", "did", "can", "could", "should", "would", "will", "have", "has"}


def b_question(g: Group, c: Ctx):
    from .phrases import tidy

    f = next((x for x in g.facts if x.question), None)
    if not f:
        return None
    t = f.text.strip()
    ws = t.split()
    if R.BN.search(t):
        ok = len(ws) >= 2
    else:
        ok = len(ws) >= 3 and (norm_token(ws[0]) in QUESTION_START or t.endswith("?"))
    q = tidy(t, 80, min_content=1, whole=True) if ok else None
    if not q:
        return None
    if not q.endswith("?") and (t.endswith("?") or norm_token(ws[0]) in QUESTION_START):
        q += "?"
    return [{"type": "question", "text": _cap(q), "options": [], "at_word": f.words[0].id}], {}


def b_pros_cons(g: Group, c: Ctx):
    from ..visuals import terms as T
    from .phrases import tidy

    f = next((x for x in g.facts if x.contrast), None)
    if not f:
        return None
    left, right, w = f.contrast
    if w.id == f.words[0].id or len(left.split()) > 6 or len(right.split()) > 6:
        return None                                            # "However, ..." against the previous sentence, or long clauses: not two clear sides
    l2, r2 = tidy(left, 30, min_content=1), tidy(right, 30, min_content=1)
    if not l2 or not r2 or l2.lower() == r2.lower():
        return None
    topics = _topics(c)
    if not R.BN.search(l2 + r2) and not (any(T.is_key_term(x, topics) for x in l2.split()) and any(T.is_key_term(x, topics) for x in r2.split())):
        return None                                            # both sides must name something
    return [{"type": "pros_cons", "pros": [_cap(l2)], "cons": [_cap(r2)], "at_word": f.words[0].id}], {}


def b_quote_card(g: Group, c: Ctx):
    from ..visuals import terms as T
    from .phrases import is_sentence, tidy

    f = next((x for x in g.facts if x.quote), None)
    if f:
        text, by = tidy(f.quote, 90, min_content=2, whole=True), f.speaker or ""
    else:
        # no quotation marks: a pull quote is only for a complete, meaningful sentence ("Black holes are not holes."), never a fragment
        f = next((x for x in g.facts if is_sentence(x.text) and 5 <= len(x.text.split()) <= 16
                  and sum(T.is_key_term(w.text, _topics(c)) for w in x.words) >= 2), None)
        text, by = (tidy(f.text, 90, min_content=2, whole=True) if f else None), (f.speaker if f else "") or ""
    if not text or len(text) < 8:
        return None
    return [{"type": "quote", "text": _cap(text), "by": clip(by, 26), "at_word": f.words[0].id}], {}


# ---- cartoon casting
LAYOUT_X = {1: [0.5], 2: [0.3, 0.7], 3: [0.2, 0.5, 0.8]}


def _cast(g: Group, c: Ctx) -> list[dict]:
    whos: list[str] = []
    for f in g.facts:
        for p in f.persons:
            if p not in whos:
                whos.append(p)
    names = [n for f in g.facts for n in f.names]
    if not whos and c.cast:
        whos = list(c.cast.keys())[:2]
    if not whos and (c.brief or {}).get("characters"):
        for ch in c.brief["characters"][:2]:
            for tok in re.findall(r"[\w']+", ch.lower()):
                if tok in R.PERSON:
                    whos.append(R.PERSON[tok])
                    break
    if not whos:
        whos = ["man"]
    whos = whos[:3]
    pose = next((f.pose for f in g.facts if f.pose != "stand"), "stand")
    exp = next((f.expression for f in g.facts if f.expression != "neutral"), "neutral")
    xs = LAYOUT_X[len(whos)]
    members = []
    for i, w in enumerate(whos):
        name = names[i] if i < len(names) else ""
        members.append({"who": w, "pose": pose if i == 0 else ("point" if pose == "walk" and i == 1 else "stand"), "expression": exp if i == 0 else "neutral",
                        "x": xs[i], "flip": i == len(whos) - 1 and len(whos) > 1, "name": name[:14]})
        c.cast[w] = {"name": name}
    return members


def b_cartoon(g: Group, c: Ctx):
    f0 = next((f for f in g.facts if f.persons or f.place), g.facts[0])
    place = next((f.place for f in g.facts if f.place), None) or c.last_set
    cast = _cast(g, c)
    c.last_set = place
    f = next((x for x in g.facts if x.quote), None)
    bubble = clip(f.quote, 70) if f else ""
    if not bubble and any(norm_token(w.text) in {"said", "asked", "replied", "বলল", "বললেন", "জিজ্ঞেস"} for w in g.words):
        m = re.search(r"[:,]\s*(.{8,})$", g.facts[0].text)
        bubble = clip(m.group(1), 70) if m else ""
    props = []
    for f2 in g.facts:
        pk = c.picks.get(f2.beat.id)
        if pk and pk.sticker and pk.sticker not in props:
            props.append(pk.sticker)
    return [{"type": "cartoon", "set": place, "cast": cast, "bubble": bubble, "speaker": 0, "props": props[:2], "at_word": f0.words[0].id}], {"highlight": f0.words[0].id}


def b_feature_grid(g: Group, c: Ctx):
    items = []
    from .phrases import tidy, tidy_all

    lst = next((f for f in g.facts if len(f.items) >= 2), None)
    if lst:
        titles = tidy_all([t for t, _ in lst.items[:4]], 22, need=2)
        if not titles:
            return None
        items = [{"title": _cap(t), "detail": ""} for t in titles]
        at = lst.items[0][1].id
    else:
        feats = [f for f in g.facts if f.role in ("feature", "claim", "proof")][:4]
        if len(feats) < 2:
            return None
        for f in feats:
            kw = _keyword(f.words, _topics(c))                  # each card is named by its sentence's key term
            if not kw:
                return None
            rest = " ".join(w.text for w in f.words if w.id != kw.id)
            items.append({"title": _cap(clip(kw.text, 22)), "detail": tidy(rest, 40, min_content=2) or ""})
        at = feats[0].words[0].id
    # A title can start with a verb that also names an unrelated object ("hide" -> animal hide).
    # Use a seeded match for such verbs, or leave the card as typography.
    from ..visuals.lexicon import Lexicon
    from ..visuals.terms import shares

    lx = Lexicon.get()
    for it in items:
        first = it["title"].split()[0] if it["title"] else ""
        m = lx.lookup(first) if lx.ok and first else None
        part_of_speech = shares(first) if first else None
        if m and m.source == "dict" and part_of_speech and part_of_speech[1] > 0.6 and part_of_speech[0] < 0.2:
            continue
        if m and m.usable() and m.sticker:
            it["emoji"] = m.sticker
        elif m and m.usable() and m.line:
            it["icon"] = m.line
    return [{"type": "feature_grid", "items": items[:4], "at_word": at}], {}


def b_price_cta(g: Group, c: Ctx):
    f = next((x for x in g.facts if "price" in x.roles and any(n["kind"] == "money" for n in x.numbers)), None)
    if f:
        nums = [n for n in f.numbers if n["kind"] == "money"] or f.numbers
        price = nums[0]
        old = nums[1]["disp"][:12] if len(nums) > 1 and any(norm_token(w.text) in {"was", "instead", "before", "আগে", "ছিল"} for w in f.words) else ""
        return [{"type": "price_tag", "price": price["disp"][:12], "old_price": old, "label": _label(price, 28), "at_word": price["word"].id}], {"highlight": price["word"].id}
    f = next((x for x in g.facts if "cta" in x.roles), None) or g.facts[-1]
    cta_w = next((w for w in f.words if norm_token(w.text) in R.CTA or any(norm_token(w.text).startswith(x) for x in R.CTA if R.BN.search(x) and len(x) >= 3)), f.words[-1])
    i = next((k for k, w in enumerate(f.words) if w.id == cta_w.id), 0)
    button = clip(" ".join(w.text for w in f.words[max(0, i - 1):i + 2]), 24)
    return [{"type": "cta", "headline": clip(f.text, 40), "button": button, "sub": "", "at_word": f.words[0].id}], {}


def b_device(g: Group, c: Ctx):
    if not g.media_id:
        return None
    kind = "phone" if g.media_ratio < 0.8 else "laptop"
    kw = _keyword(g.words, _topics(c))
    calls = []
    cands = [w for w in g.words if len(norm_token(w.text)) >= 4 and norm_token(w.text) not in R.DETERMINERS][:2]
    for k, w in enumerate(cands[:2]):
        calls.append({"text": clip(w.text, 24), "x": [0.32, 0.66][k], "y": [0.3, 0.68][k]})
    return [{"type": "device", "kind": kind, "media": g.media_id, "caption": clip(kw.text if kw else "", 40), "callouts": calls, "at_word": g.first_word().id}], {}


def b_media_hero(g: Group, c: Ctx):
    if not g.media_id:
        return None
    pk = next((c.picks[f.beat.id] for f in g.facts if f.beat.id in c.picks), None)
    kw = _keyword(g.words, _topics(c))
    els = []
    if pk and pk.kind != "text":
        els.append({"type": "keyword", "text": clip(pk.text, 30), "style": "highlight", "at_word": pk.word_id})
    elif kw:
        els.append({"type": "keyword", "text": clip(kw.text, 30), "style": "highlight", "at_word": kw.id})
    n = g.numbers[:1]
    if n:                                                      # a number that was said stays on screen, over the picture
        els.insert(0, {"type": "big_number", "value": n[0]["disp"].rstrip("%")[:12], "unit": "%" if n[0]["kind"] == "percent" else "", "label": _label(n[0], 40), "at_word": n[0]["word"].id})
        els = els[:2]
    item = c.media.get(g.media_id)
    layout = "lower"
    if item and item.faces:
        from .media import text_layout

        layout = text_layout(item, c.aspect)               # people low in the frame: the text goes above them
    return els, {"layout": layout, "backdrop": {"media": g.media_id, "motion": "kenburns"}}


def b_media_frame(g: Group, c: Ctx):
    if not g.media_id:
        return None
    frame = ("rounded", "polaroid", "tv", "plain")[c.pattern % 4]
    kw = _keyword(g.words, _topics(c))
    els = [{"type": "media_frame", "media": g.media_id, "frame": frame, "caption": clip(kw.text if kw else "", 40), "motion": "kenburns", "at_word": g.first_word().id}]
    return els, {}


def b_speaker(g: Group, c: Ctx):
    f = g.facts[0]
    if not f.speaker:
        return None
    if f.speaker not in c.speakers:
        c.speakers.append(f.speaker)
    idx = c.speakers.index(f.speaker)
    return [{"type": "speaker_card", "name": clip(f.speaker, 20), "text": clip(g.text, 90), "side": "left" if idx % 2 == 0 else "right", "color": idx % 6,
             "at_word": f.words[0].id}], {"layout": "stack"}


def _topics(c):
    """How often each word is said in the whole video (cached on the context)."""
    if getattr(c, "_topics", None) is None:
        from ..visuals.terms import topic_counts

        c._topics = topic_counts(w.text for w in c.words.values())
    return c._topics


def b_picture(g: Group, c: Ctx):
    """One or more pictures for the stressed words (the original style); the local AI refines these scenes."""
    scene_picks = sorted((c.picks[f.beat.id] for f in g.facts if f.beat.id in c.picks), key=lambda k: -k.score)
    primary = scene_picks[0] if scene_picks else None
    els: list[dict] = []
    if primary:
        els = _visual_elements(primary, c.pattern, c.words[primary.word_id], g.dur >= 6.5)
        used = {primary.sticker or primary.line}
        for k in (x for f in g.facts for x in (c.picks[f.beat.id].extras if f.beat.id in c.picks else [])):
            vid = k["sticker"] or k["line"]
            if len(els) >= 3 or vid in used:
                continue
            used.add(vid)
            els.append({"type": "sticker", "emoji": k["sticker"], "label": k["text"][:26], "at_word": k["word_id"]} if k["sticker"] else
                       {"type": "icon", "name": k["line"], "label": k["text"][:26], "at_word": k["word_id"]})
        els.sort(key=lambda e: c.words[e["at_word"]].start)
        return els, {"highlight": primary.word_id}
    kw = _keyword(g.words, _topics(c))
    if not kw:
        return None
    return [{"type": "keyword", "text": clip(kw.text, 30), "style": ("underline", "highlight", "stamp")[c.pattern % 3], "at_word": kw.id}], {"highlight": kw.id}


# ---- diagrams
def b_flow(g: Group, c: Ctx):
    f = next((x for x in g.facts if len(x.flow) >= 3), None)
    if not f:
        return None
    nodes = [{"text": clip(t, 22), "kind": "start" if i == 0 else "end" if i == len(f.flow) - 1 else "step"} for i, t in enumerate(f.flow[:5])]
    return [{"type": "flow", "nodes": nodes, "at_word": f.words[0].id}], {}


def b_cycle(g: Group, c: Ctx):
    f = next((x for x in g.facts if "cycle" in x.cues and len(x.items) >= 3), None)
    if not f:
        return None
    return [{"type": "cycle", "items": [clip(t, 16) for t, _ in f.items[:6]], "center": clip((c.brief or {}).get("topic", ""), 20) if g.facts[0].first else "", "at_word": f.items[0][1].id}], {}


def b_hierarchy(g: Group, c: Ctx):
    f = next((x for x in g.facts if "hierarchy" in x.cues and len(x.items) >= 2), None)
    if not f:
        return None
    pre = re.split(r"(?i)\b(?:types of|kinds of|categories|consists of|divided into|made up of|split into|branches into)\b", f.text)[0]
    root = clip(" ".join(w for w in pre.split() if w.lower() not in R.DETERMINERS)[-22:], 22) or clip((c.brief or {}).get("topic", "") or "Types", 22)
    return [{"type": "hierarchy", "root": root, "branches": [{"text": clip(t, 20), "children": []} for t, _ in f.items[:4]], "at_word": f.words[0].id}], {}


def b_venn(g: Group, c: Ctx):
    f = next((x for x in g.facts if "venn" in x.cues), None)
    if not f:
        return None
    m = re.search(r"(?:between\s+)?([\w\u0980-\u09FF]+(?:\s[\w\u0980-\u09FF]+)?)\s+(?:and|আর|এবং)\s+([\w\u0980-\u09FF]+(?:\s[\w\u0980-\u09FF]+)?)", f.text)
    items = [clip(t, 16) for t, _ in f.items[:3]] if len(f.items) >= 2 else ([clip(m.group(1), 16), clip(m.group(2), 16)] if m else [])
    items = [i for i in items if i and i.lower() not in R.DETERMINERS]
    if len(items) < 2:
        return None
    ov = re.search(r"(?:share|in common|both have|both|কমন)\s+(?:a\s+|an\s+|the\s+)?([\w\u0980-\u09FF]+)", f.text, re.I)
    return [{"type": "venn", "sets": items[:3], "overlap": clip(ov.group(1), 16) if ov else "", "at_word": f.words[0].id}], {}


def b_funnel(g: Group, c: Ctx):
    nums = g.numbers
    if len(nums) >= 3 and all(_num_val(nums[i]) >= _num_val(nums[i + 1]) for i in range(len(nums) - 1)):
        return [{"type": "funnel", "stages": [{"label": _label(n, 20) or "·", "value": _fmt(n["disp"])[:10]} for n in nums[:5]], "at_word": nums[0]["word"].id}], {}
    f = next((x for x in g.facts if "funnel" in x.cues and len(x.items) >= 3), None)
    if f:
        return [{"type": "funnel", "stages": [{"label": clip(t, 20), "value": ""} for t, _ in f.items[:5]], "at_word": f.items[0][1].id}], {}
    return None


def b_pyramid(g: Group, c: Ctx):
    f = next((x for x in g.facts if "pyramid" in x.cues and len(x.items) >= 3), None)
    if not f:
        return None
    return [{"type": "pyramid", "levels": [clip(t, 22) for t, _ in f.items[:5]], "at_word": f.items[0][1].id}], {}


def b_matrix(g: Group, c: Ctx):
    f = next((x for x in g.facts if "matrix" in x.cues and len(x.items) == 4), None)
    if not f:
        return None
    return [{"type": "matrix", "x_label": "", "y_label": "", "quadrants": [clip(t, 18) for t, _ in f.items], "at_word": f.items[0][1].id}], {}


def b_pictogram(g: Group, c: Ctx):
    f = next((x for x in g.facts if x.ratio), None)
    if not f:
        return None
    a, b = f.ratio
    total, hi = (b, a) if b <= 20 else (10, max(1, round(a / b * 10)))
    pk = c.picks.get(f.beat.id)
    em = pk.sticker if pk and pk.sticker and pk.kind == "sticker" else "1f9d1"
    return [{"type": "pictogram", "total": total, "highlighted": hi, "emoji": em, "label": clip(f.text, 36), "at_word": f.words[0].id}], {"highlight": f.words[0].id}


def b_gauge(g: Group, c: Ctx):
    f = next((x for x in g.facts if "gauge" in x.cues and x.numbers), None)
    if not f:
        return None
    n = f.numbers[0]
    raw = re.sub(r"[^\d.]", "", n["disp"].translate(BN_DIG))
    try:
        v = float(raw)
    except ValueError:
        return None
    m = re.search(r"out of\s*(\d+)", f.text.translate(BN_DIG))
    if m and float(m.group(1)) > 0:
        v = v / float(m.group(1)) * 100
    if not 0 <= v <= 100:
        return None
    bn = c.language == "bn"
    return [{"type": "gauge", "value": round(v, 1), "label": _label(n, 30), "low": "কম" if bn else "Low", "high": "বেশি" if bn else "High", "display": n["disp"][:10], "at_word": n["word"].id}], {"highlight": n["word"].id}


# ------------------------------------------------------------------ fit functions (0 = cannot, 1 = ideal)
def f_title_card(g, c):
    return 0.9 if g.facts[0].first and g.dur < 7 else (0.15 if g.role == "hook" else 0.0)


def f_hero_number(g, c):
    n = g.numbers
    if not n:
        return 0.0
    return 1.0 if any(x["kind"] == "money" for x in n) else (0.8 if len(n) == 1 else 0.6)


def f_ring(g, c):
    p = [n for n in g.numbers if n["kind"] == "percent"]
    return 1.0 if len(p) == 1 else (0.6 if p else 0.0)


def f_stat_row(g, c):
    n = len(g.numbers)
    return 0.0 if n < 2 else (1.0 if n >= 3 else 0.7)


def f_bar_compare(g, c):
    n = g.numbers
    if len(n) < 2:
        return 0.0
    same = len({x["kind"] for x in n}) == 1
    return (0.95 if same else 0.4) * (1.0 if 2 <= len(n) <= 5 else 0.5)


def f_line_trend(g, c):
    n = len(g.numbers)
    if n < 3:
        return 0.0
    return 1.0 if any(f.trend for f in g.facts) or len(g.years) >= 3 else 0.5


def f_timeline(g, c):
    return 1.0 if len(g.years) >= 3 else (0.9 if len(g.years) == 2 else 0.0)


def f_steps(g, c):
    st = sum(1 for f in g.facts if "step" in f.roles)
    if st >= 2:
        return 1.0
    return 0.7 if any(len(f.items) >= 3 for f in g.facts) else 0.0


def f_checklist(g, c):
    has_list = any(len(f.items) >= 3 for f in g.facts)
    return (1.0 if "recap" in g.roles else 0.8) if has_list else 0.0


def f_definition(g, c):
    return 1.0 if any(f.definition for f in g.facts) else 0.0


def f_question(g, c):
    return 0.9 if any(f.question for f in g.facts) and g.dur < 8 else 0.0


def f_pros_cons(g, c):
    return 0.8 if any(f.contrast and len(f.contrast[0]) >= 3 and len(f.contrast[1]) >= 3 for f in g.facts) else 0.0


def f_quote_card(g, c):
    if any(f.quote for f in g.facts):
        return 1.0
    return 0.25 if g.dur < 6 and g.role == "claim" else 0.0


def f_cartoon(g, c):
    people = any(f.persons or f.names for f in g.facts)
    place = any(f.place for f in g.facts)
    act = any(f.pose != "stand" for f in g.facts)
    if people and (place or act):
        return 1.0
    if people or (place and act):
        return 0.7
    return 0.25 if c.cast else 0.0


def f_feature_grid(g, c):
    if any(len(f.items) >= 2 for f in g.facts):
        return 0.95
    feats = sum(1 for f in g.facts if f.role in ("feature", "proof"))
    return 0.9 if feats >= 2 else 0.0


def f_price_cta(g, c):
    if any("price" in f.roles and any(n["kind"] == "money" for n in f.numbers) for f in g.facts):
        return 1.0
    return 1.0 if "cta" in g.roles else 0.0


def f_device(g, c):
    return 1.0 if g.media_id and c.usecase == "product" else 0.0


def f_media_hero(g, c):
    return 1.0 if g.media_id else 0.0


def f_media_frame(g, c):
    return 0.9 if g.media_id else 0.0


def f_speaker(g, c):
    return 1.0 if g.facts[0].speaker else 0.0


def f_flow(g, c):
    return 1.0 if any(len(f.flow) >= 3 for f in g.facts) else 0.0


def f_cycle(g, c):
    return 1.0 if any("cycle" in f.cues and len(f.items) >= 3 for f in g.facts) else 0.0


def f_hierarchy(g, c):
    return 1.0 if any("hierarchy" in f.cues and len(f.items) >= 2 for f in g.facts) else 0.0


def f_venn(g, c):
    return 0.9 if any("venn" in f.cues for f in g.facts) and b_venn(g, c) else 0.0


def f_funnel(g, c):
    nums = g.numbers
    if len(nums) >= 3 and all(_num_val(nums[i]) >= _num_val(nums[i + 1]) for i in range(len(nums) - 1)) and any("funnel" in f.cues for f in g.facts):
        return 1.0
    return 0.9 if any("funnel" in f.cues and len(f.items) >= 3 for f in g.facts) else 0.0


def f_pyramid(g, c):
    return 1.0 if any("pyramid" in f.cues and len(f.items) >= 3 for f in g.facts) else 0.0


def f_matrix(g, c):
    return 0.9 if any("matrix" in f.cues and len(f.items) == 4 for f in g.facts) else 0.0


def f_pictogram(g, c):
    return 1.0 if any(f.ratio for f in g.facts) else 0.0


def f_gauge(g, c):
    return 0.9 if any("gauge" in f.cues and f.numbers for f in g.facts) else 0.0


def f_picture(g, c):
    return 0.7


@dataclass
class Archetype:
    name: str
    fit: Callable[[Group, Ctx], float]
    build: Callable[[Group, Ctx], Optional[tuple[list[dict], dict]]]
    family: str
    big: bool = False             # a "big moment": hero visuals that should come at least every few scenes
    repeat_ok: bool = False       # may appear in consecutive scenes (speaker cards follow the conversation)


ARCHETYPES: dict[str, Archetype] = {a.name: a for a in [
    Archetype("title_card", f_title_card, b_title_card, "title", True),
    Archetype("hero_number", f_hero_number, b_hero_number, "number", True),
    Archetype("ring", f_ring, b_ring, "chart", True),
    Archetype("stat_row", f_stat_row, b_stat_row, "number", True),
    Archetype("bar_compare", f_bar_compare, b_bar_compare, "chart"),
    Archetype("line_trend", f_line_trend, b_line_trend, "chart", True),
    Archetype("timeline", f_timeline, b_timeline, "structure"),
    Archetype("steps", f_steps, b_steps, "structure"),
    Archetype("checklist", f_checklist, b_checklist, "structure"),
    Archetype("definition", f_definition, b_definition, "text"),
    Archetype("question", f_question, b_question, "text"),
    Archetype("pros_cons", f_pros_cons, b_pros_cons, "structure"),
    Archetype("quote_card", f_quote_card, b_quote_card, "text"),
    Archetype("cartoon", f_cartoon, b_cartoon, "cartoon", True),
    Archetype("feature_grid", f_feature_grid, b_feature_grid, "grid", True),
    Archetype("price_cta", f_price_cta, b_price_cta, "offer", True),
    Archetype("device", f_device, b_device, "media", True),
    Archetype("media_hero", f_media_hero, b_media_hero, "media", True),
    Archetype("media_frame", f_media_frame, b_media_frame, "media"),
    Archetype("speaker", f_speaker, b_speaker, "speaker", False, True),
    Archetype("flow", f_flow, b_flow, "diagram"),
    Archetype("cycle", f_cycle, b_cycle, "diagram"),
    Archetype("hierarchy", f_hierarchy, b_hierarchy, "diagram"),
    Archetype("venn", f_venn, b_venn, "diagram"),
    Archetype("funnel", f_funnel, b_funnel, "diagram"),
    Archetype("pyramid", f_pyramid, b_pyramid, "diagram"),
    Archetype("matrix", f_matrix, b_matrix, "diagram"),
    Archetype("pictogram", f_pictogram, b_pictogram, "chart", True),
    Archetype("gauge", f_gauge, b_gauge, "chart"),
    Archetype("picture", f_picture, b_picture, "picture"),
]}
