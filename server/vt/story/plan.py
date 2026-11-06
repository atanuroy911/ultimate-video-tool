"""Cartoon 2: our words -> the story engine's planner -> our scene plan, and back.

The story engine (ported unchanged in engine_rules.py / engine_validate.py) thinks in captions with seconds and writes a spec
{characters, captions, speak, tags, sfx, scenes:[{s, e, bg, elements}]}. Here:
  captions_from_words  the edited transcript as short clause captions (the engine cuts scenes between captions, so they must be short)
  draft_spec           the rule planner's spec (always works: it is the fallback for every AI)
  to_scenes            a spec -> ScenesFile: one Scene per story scene holding one `story` element, beats assigned by time,
                       sounds as word cues, the cast shared by all scenes
  to_spec              ScenesFile -> spec (what a director edits; also what the Studio shows as "the story")
  apply_spec           validate a spec from any director and make it the plan
"""
from __future__ import annotations

import copy
import re
from typing import Any, Optional

from ..schema import Beats, Scene, ScenesFile, Story, StoryCharacter, Transcript
from . import catalog as SC
from . import engine_rules as R
from . import engine_validate as V

MAX_CAPTION = 42          # characters in one caption unit
PAUSE = 0.35              # a pause this long ends a unit
_END = re.compile(r"[.?!।;:,]['\"”’)]*$")
_OPEN = ("\"", "“", "‘")
_CLOSE = ("\"", "”", "’")


def captions_from_words(tr: Transcript, cues: list[dict] | None = None) -> list[dict]:
    """Short caption units from the kept words: a unit ends at punctuation, at a pause, or when it gets long. Quoted speech is marked, as the
    engine's planner expects (it gives the line to the person named just before). With the person's own subtitle file (`cues`, from
    ingest.attach_subtitles) each subtitle line is one unit, as the story engine planned from its SRT."""
    if cues:
        caps = _captions_from_cues(tr, cues)
        if caps:
            return caps
    caps: list[dict] = []
    cur: list = []
    quoted = False

    def close():
        nonlocal cur
        if cur:
            text = " ".join(w.text for w in cur).strip()
            caps.append({"s": round(cur[0].start, 2), "e": round(cur[-1].end, 2), "t": text, "quote": quote_of(cur), "words": [w.id for w in cur]})
        cur = []

    starts_quote: dict[str, bool] = {}

    def quote_of(ws) -> bool:
        return any(starts_quote.get(w.id) for w in ws)

    words = tr.kept()
    for i, w in enumerate(words):
        if cur and (w.start - cur[-1].end >= PAUSE or len(" ".join(x.text for x in cur)) + len(w.text) > MAX_CAPTION):
            close()
        if w.text.startswith(_OPEN):
            quoted = True
        starts_quote[w.id] = quoted
        cur.append(w)
        if w.text.rstrip(".,!?।;:").endswith(_CLOSE) or (w.text.endswith(_CLOSE) and quoted):
            quoted = False
            close()
        elif _END.search(w.text):
            close()
    close()
    return caps


def _captions_from_cues(tr: Transcript, cues: list[dict]) -> list[dict]:
    """The transcript's words were made from the subtitle lines in order, `n` words per line: give each line back its words (their times follow
    any pause the edit removed, and a word the person deleted is left out)."""
    words, at, caps = tr.words, 0, []
    for c in cues:
        group = [w for w in words[at:at + int(c.get("n") or 0)] if not w.cut]
        at += int(c.get("n") or 0)
        if group:
            caps.append({"s": round(group[0].start, 2), "e": round(group[-1].end, 2), "t": " ".join(w.text for w in group),
                         "quote": group[0].text.startswith(_OPEN), "words": [w.id for w in group]})
    return caps if at == len(words) else []                 # the words were re-split since: fall back to the clause captions


ROLE_EN = {"mother": "Mom", "father": "Dad", "grandfather": "Grandpa", "grandmother": "Grandma", "teacher": "Teacher", "friend": "Friend",
           "sister": "Sister", "wife": "Wife", "husband": "Husband"}


def hero_is_female(tr: Transcript) -> bool:
    """English pronouns tell whether the story's main person is a woman (Bangla pronouns do not; the person can change the look in the cast)."""
    toks = [w.text.lower().strip(".,!?;:\"'“”’") for w in tr.kept()]
    she = sum(t in ("she", "her", "hers", "herself") for t in toks)
    he = sum(t in ("he", "him", "his", "himself") for t in toks)
    return she > he


def draft_spec(tr: Transcript, total: float, language: str = "en", cues: list[dict] | None = None) -> tuple[dict, list[dict]]:
    """The rule planner's spec and the caption units it was made from (with their word ids)."""
    caps = captions_from_words(tr, cues)
    if not caps:
        raise ValueError("there are no spoken words to plan a story from")
    spec = R.plan(copy.deepcopy([{k: v for k, v in c.items() if k != "words"} for c in caps]), round(total, 2),
                  lang=language if language in ("bn", "en") else "en", hero_female=hero_is_female(tr))
    if language != "bn":                               # the engine's role names are Bangla; an English story calls them in English
        for cid, ch in spec["characters"].items():
            if cid in ROLE_EN and ch.get("name") == R.ROLES[cid][1]:
                ch["name"] = ROLE_EN[cid]
    spec, errors, _ = V.validate(spec)
    if errors:
        raise ValueError("; ".join(errors[:4]))
    return spec, caps


def _nearest_word(words: list, t: float, lo: float = -1e9, hi: float = 1e9) -> Optional[str]:
    inside = [w for w in words if lo <= w.start < hi] or words
    return min(inside, key=lambda w: abs(w.start - t)).id if inside else None


def to_scenes(spec: dict, tr: Transcript, beats: Beats, caps: list[dict], planner: str = "rules", theme: str = "paper") -> ScenesFile:
    words = tr.kept()
    by_word = {w.id: w for w in words}
    scenes_in = sorted(spec["scenes"], key=lambda x: x["s"])
    beat_start = [(b, by_word[b.word_ids[0]].start if b.word_ids and b.word_ids[0] in by_word else b.start) for b in beats.beats]
    out: list[Scene] = []
    for i, sc in enumerate(scenes_in):
        s, e = float(sc["s"]), float(sc["e"])
        last = i == len(scenes_in) - 1
        mine = [b.id for b, t in beat_start if (t >= s or i == 0) and (t < e or last)]
        taken = {bid for x in out for bid in x.beats}
        mine = [bid for bid in mine if bid not in taken]
        tag = next((tg["tag"] for tg in spec.get("tags", []) if tg["s"] <= s + 0.01 < tg["e"]), "")
        speak = {cid: [[a, b] for a, b in spans if b > s and a < e] for cid, spans in (spec.get("speak") or {}).items()}
        speak = {k: v for k, v in speak.items() if v}
        at_word = _nearest_word(words, s, s, e) or words[0].id
        story = Story(at_word=at_word, bg=sc.get("bg") or {"type": "plain"}, items=sc.get("elements", []), tag=str(tag)[:24],
                      push=float(sc.get("push", 0.05)), speak=speak, edited=planner in ("manual",))
        sfx = []
        for name, t, _vol in [f for f in spec.get("sfx", []) if s <= f[1] < e]:
            wid = _nearest_word(words, t, s, e)
            if wid and name in SC.SFX:
                sfx.append({"at_word": wid, "id": SC.SFX[name]})
        highlight = _highlights(caps, spec, s, e, set(w for bid in mine for b in beats.beats if b.id == bid for w in b.word_ids), by_word)
        out.append(Scene(id=f"s{i + 1}", beats=mine, start=None if i == 0 else round(s, 3), layout="hero", transition_in="cut",
                         transition_effect="none", camera_move="none", archetype="story", role=(sc.get("note") or "").split(":")[0][:24] or None,
                         elements=[story], sfx=sfx, caption={"highlight_words": highlight}))
    cast = {k: StoryCharacter.model_validate({f: v for f, v in c.items() if f in StoryCharacter.model_fields}) for k, c in spec.get("characters", {}).items()}
    return ScenesFile(theme=theme, planner=planner, scenes=out, story_cast=cast)


def _highlights(caps: list[dict], spec: dict, s: float, e: float, scene_words: set, by_word: dict) -> list[str]:
    """The engine marks one or two key words per caption with {braces}; those become our caption highlights."""
    out = []
    for c, sc in zip(caps, spec.get("captions", [])):
        if not (s <= c["s"] < e):
            continue
        keys = {k.strip(".,!?।“”\"'").lower() for k in re.findall(r"\{([^}]+)\}", sc.get("t", ""))}
        for wid in c["words"]:
            if wid in scene_words and by_word[wid].text.strip(".,!?।“”\"'").lower() in keys:
                out.append(wid)
    return out[:4]


def to_spec(sf: ScenesFile, beats: Beats, total: float, language: str = "en") -> dict:
    """The plan as one story-engine spec (absolute seconds), including every edit made in the Studio: what an outside director reads and edits."""
    from ..compose import scene_timing

    timing = {t["id"]: t for t in scene_timing(sf, beats, total)}
    scenes, tags, speak, sfx = [], [], {}, []
    for sc in sf.scenes:
        st = next((e for e in sc.elements if e.type == "story"), None)
        if st is None:
            continue
        s, e = timing[sc.id]["start"], timing[sc.id]["end"]
        scenes.append({"s": s, "e": e, "bg": st.bg, "push": st.push, "elements": [i.model_dump(exclude_none=True) for i in st.items]})
        if st.tag:
            tags.append({"s": s, "e": e, "tag": st.tag})
        for k, spans in st.speak.items():
            speak.setdefault(k, []).extend(spans)
    return {"meta": {"total": round(total, 2), "lang": language}, "characters": {k: v.model_dump(exclude_none=True) for k, v in sf.story_cast.items()},
            "speak": speak, "tags": tags, "sfx": sfx, "scenes": scenes}


def check_scene(out: Any, s: float, e: float, characters: dict) -> list[str]:
    """Problems in one designed scene, in words a model can fix (the engine's validator plus our schema)."""
    if not isinstance(out, dict):
        return ["the answer must be a JSON object with bg and elements"]
    test = {"meta": {"total": e}, "characters": characters, "captions": [], "scenes": [{"s": 0.0 if s < 0.01 else s, "e": e, "bg": out.get("bg") or {"type": "plain"},
                                                                                      "elements": out.get("elements") or []}]}
    if s >= 0.01:
        test["scenes"].insert(0, {"s": 0.0, "e": s, "bg": {"type": "plain"}, "elements": []})
    _, errors, warnings = V.validate(test, None, fix=False)
    errors = [x for x in errors if "gap/overlap" not in x]
    if not out.get("elements"):
        errors.append("elements list is empty")
    try:
        Story(at_word="w", bg=out.get("bg") or {"type": "plain"}, items=out.get("elements") or [])
    except Exception as ex:                                     # pydantic's message names the field
        errors.append(str(ex).split("\n", 1)[-1][:300])
    return errors + [w for w in warnings if "outside" in w or "safe zone" in w][:4]
