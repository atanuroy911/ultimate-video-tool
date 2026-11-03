"""The plan the person sees and approves before anything expensive starts (docs/plans/PLAN-DIRECTOR-MODULES.MD section 8).

A PlanDoc is built from what the director already understood (the reading and the slots of `vt/reel/`), with no GPU and no AI call of its own. It is a *view over the same
decisions the maker will use*: when the person approves it, `vt/reel/plan.py::build_reel_plan` draws exactly these moments with exactly these prompts. Every change is one typed
operation (`apply_edit`) that is validated, re-estimated and logged by the caller as the person's call; locked moments are never changed by a later re-plan.

Words on screen are the plain ones ("moment", "where the picture changes", "made for you"); the internal names stay in the file.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ..util import now_iso, read_json, write_json

PLAN = "plan_doc.json"
MEDIA = ("made", "repeat", "card")
MEDIUM_LABEL = {"made": "Made for you", "repeat": "Same picture again", "card": "Word card"}
ALT_WHY = {"made": "Draws a new picture for this moment: a few seconds on the picture server.", "repeat": "Keeps the picture before it, moved a little: no drawing time.",
           "card": "Shows the key word on a plain card: no drawing time."}
PACE = {"punchy": 0.75, "balanced": 1.0, "calm": 1.35}
DEFAULT_STILL_SECONDS = 8.0                       # when no picture has been drawn yet on this server (measured: 4 to 12 s a picture on the V100)
ASSEMBLE_BASE, ASSEMBLE_PER_MOMENT = 20.0, 1.5    # putting it together: sound, captions, render (seconds)
EXPENSIVE_MOMENTS = 3                             # "when expensive": at least this many pictures to draw


class WordRef(BaseModel):
    id: str
    text: str
    stress: float = 0.0                           # 0 to 1: how strongly the word carries the sentence (the director's emphasis word is 1)


class BeatRef(BaseModel):
    word_id: str = ""
    time: float = 0.0
    kind: Literal["emphasis", "number", "first"] = "first"
    strength: float = 0.3
    why: str = ""


class Alt(BaseModel):
    medium: str
    why: str


class Moment(BaseModel):
    id: str
    start: float
    end: float
    sentence_ids: list[str]
    text: str
    words: list[WordRef] = Field(default_factory=list)
    beat: BeatRef = Field(default_factory=BeatRef)
    medium: Literal["made", "repeat", "card"] = "made"
    alternatives: list[Alt] = Field(default_factory=list)
    draw: str = ""                                # what the picture shows, in plain words: the person edits this
    place: str = ""                               # one of Idea.places: where it happens; its description goes into the picture prompt
    why: str = ""                                 # the director's one line
    card: str = ""                                # a chapter label ("STEP 2") that sits on the picture
    turn: bool = False
    locked: bool = False
    status: Literal["planned", "waiting", "making", "ready", "replaced", "failed"] = "planned"
    media: str = ""                               # the picture once it exists (a media id)
    problem: str = ""
    seconds_taken: float = 0.0
    preview: str = ""                             # a media id of a preview picture, when the person asked for one

    @property
    def seconds(self) -> float:
        return max(0.0, self.end - self.start)


class Idea(BaseModel):
    goal: str = ""
    audience: str = "People who watch short videos"
    tone: str = ""
    kind: str = "explanation"
    style: str = "cartoon"
    style_why: str = ""
    character: str = ""
    places: dict[str, str] = Field(default_factory=dict)       # name -> how the place looks and how big its things are: every picture is painted alone
    cast: dict[str, str] = Field(default_factory=dict)         # name -> how the person looks; a prompt gets the look of each name it mentions
    pace: Literal["punchy", "balanced", "calm"] = "balanced"
    hook: str = ""
    hook_strength: float = 0.0


class Budget(BaseModel):
    n_generated: Optional[int] = Field(default=None, ge=0, le=200, description="how many pictures to make; None = one for every moment that asks for one")


class Line(BaseModel):
    label: str
    count: int = 0
    seconds: float = 0.0
    where: str = ""


class Estimate(BaseModel):
    lines: list[Line] = Field(default_factory=list)
    total_seconds: float = 0.0
    made: int = 0
    gpu_seconds: float = 0.0


class PlanDoc(BaseModel):
    version: int = 1
    rev: int = 0                                  # bumped by every edit
    state: Literal["draft", "approved", "running", "done", "declined"] = "draft"
    source: str = "rules"
    idea: Idea = Field(default_factory=Idea)
    moments: list[Moment] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    estimate: Estimate = Field(default_factory=Estimate)
    notes: list[str] = Field(default_factory=list)
    edits: list[int] = Field(default_factory=list)           # seq numbers of the calls that changed it (the log has the rest)
    created_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    still_seconds: float = DEFAULT_STILL_SECONDS

    def moment(self, mid: str) -> Moment:
        for m in self.moments:
            if m.id == mid:
                return m
        raise PlanError(f"there is no moment '{mid}'")


class PlanError(ValueError):
    """An edit that cannot be done; the message is a sentence the person can read."""


# ----------------------------------------------------------------------------- reading and writing
def path(project_dir) -> Any:
    return project_dir / PLAN


def load(project_dir) -> Optional[PlanDoc]:
    raw = read_json(path(project_dir), None)
    if not raw:
        return None
    try:
        return PlanDoc.model_validate(raw)
    except Exception:                                                                   # noqa: BLE001 - a plan from a broken edit must not break the page
        return None


def save(project_dir, plan: PlanDoc) -> PlanDoc:
    plan.estimate = estimate(plan)
    write_json(path(project_dir), plan.model_dump())
    return plan


# ----------------------------------------------------------------------------- building
def _norm(w: str) -> str:
    return re.sub(r"[^\w$%]+", "", w.lower())


def _tone(kind: str) -> str:
    return {"steps": "Clear and practical", "story": "Personal, moving along", "explanation": "Calm and clear", "argument": "Direct, a little pointed",
            "list": "Quick and light", "opinion": "Direct and confident"}.get(kind, "Clear")


def _moment_from_slot(slot, words_by_id: dict, style: str, character: str, still_prompt_note: str = "") -> Moment:
    from ..reel.plan import _draw_for, _emphasis_word

    wid = _emphasis_word(slot, words_by_id)
    word_ids = [w for b in slot.beats for w in b.word_ids if (words_by_id.get(w) is not None and not words_by_id[w].cut)]
    emph = _norm(next((n.emphasis for n in slot.notes if n and n.emphasis), ""))
    refs = []
    for w in word_ids:
        t = words_by_id[w].text
        stress = 1.0 if w == wid else 0.6 if re.search(r"\d", t) else 0.25 if len(_norm(t)) > 5 else 0.05
        refs.append(WordRef(id=w, text=t, stress=stress))
    first = word_ids[0] if word_ids else ""
    if wid:
        beat = BeatRef(word_id=wid, time=round(words_by_id[wid].start, 2), kind="emphasis", strength=1.0,
                       why=f"The picture changes on “{words_by_id[wid].text}”, the word that carries this sentence.")
    elif any(r.stress >= 0.6 for r in refs):
        r = max(refs, key=lambda r: r.stress)
        beat = BeatRef(word_id=r.id, time=round(words_by_id[r.id].start, 2), kind="number", strength=r.stress, why=f"The picture changes on “{r.text}”, the number.")
    else:
        beat = BeatRef(word_id=first, time=round(words_by_id[first].start, 2) if first else slot.start, kind="first", strength=0.3,
                       why="Nothing in this sentence stands out, so the picture changes as it begins.")
    draw = _draw_for(slot)
    why = ("A new point starts here, so it gets a new picture." if slot.turn else "A chapter label, so the picture changes and the label sits on it." if slot.card
           else "One picture for this stretch of speech.")
    alts = [Alt(medium="repeat", why="Keeps the picture before it, moved a little: no drawing time."),
            Alt(medium="card", why=f"Shows the key word on a plain card: {emph or 'the first words'}.")]
    return Moment(id=slot.id, start=round(slot.start, 2), end=round(slot.end, 2), sentence_ids=[b.id for b in slot.beats], text=" ".join(b.text for b in slot.beats),
                  words=refs, beat=beat, medium="made", alternatives=alts, draw=draw, why=why, card=slot.card, turn=slot.turn,
                  place=next((getattr(n, "place", "") for n in slot.notes if n and n.draw == draw and getattr(n, "place", "")), "")
                  or next((getattr(n, "place", "") for n in slot.notes if n and getattr(n, "place", "")), ""))      # the director's place for this picture


def build(project, *, use_ai: bool = True, pace: str = "balanced", provider=None) -> PlanDoc:
    """The draft plan for a reel: read the script, one look, the moments. No picture is drawn and no GPU is touched. The reading is cached by the caller (reel_reading.json)."""
    from ..reel.plan import READING
    from ..reel.reading import Reading, read_script
    from ..reel.style import FIGURE, STYLES

    meta = project.meta()
    tr, beats = project.transcript(), project.beats().beats
    if not beats:
        raise PlanError("there are no sentences to plan yet")
    reading_raw = read_json(project.dir / READING, None)
    reading = Reading.model_validate(reading_raw) if reading_raw else read_script(beats, use_ai=use_ai, provider=provider)
    style = meta.options.reel_style if meta.options.reel_style in STYLES else reading.style if reading.style in STYLES else "cartoon"
    reading.character = reading.character.strip() or FIGURE.get(style, "")
    write_json(project.dir / READING, reading.model_dump())
    slots = _slots(beats, reading, pace)
    words = tr.by_id()
    moments = [_moment_from_slot(s, words, style, reading.character) for s in slots]
    plan = PlanDoc(
        source=reading.source, created_at=now_iso(), still_seconds=measured_still_seconds(project),
        idea=Idea(goal=_goal(reading, beats), kind=reading.kind, tone=_tone(reading.kind), style=style, style_why=reading.style_why, character=reading.character, places=dict(reading.places), cast=dict(reading.cast), pace=pace,
                  hook=reading.hook.text, hook_strength=reading.hook.strength),
        moments=moments, notes=list(reading.warnings))
    return save(project.dir, plan)


def _goal(reading, beats) -> str:
    return (reading.hook.text or (beats[0].text if beats else "")).strip()[:200]


def _slots(beats, reading, pace: str):
    """The slots at a pace: punchy makes more, shorter pictures; calm fewer, longer ones (never past the three-second rule's own limit)."""
    from ..reel import slots as S

    f = PACE.get(pace, 1.0)
    if f == 1.0:
        return S.build_slots(beats, reading)
    saved = dict(S.PACE)
    try:
        for k, (target, longest, fewest) in saved.items():
            S.PACE[k] = (max(3, round(target * f)), min(longest, 3.0) if f <= 1 else longest, fewest)
        return S.build_slots(beats, reading)
    finally:
        S.PACE.clear()
        S.PACE.update(saved)


def measured_still_seconds(project) -> float:
    """The median time a picture took on this server the last time (reel_report.json), else the default."""
    rep = read_json(project.dir / "reel_report.json", {}) or {}
    t = sorted(float(s.get("drawn_in") or 0) for s in rep.get("slots", []) if s.get("drawn_in"))
    return round(t[len(t) // 2], 1) if t else DEFAULT_STILL_SECONDS


# ----------------------------------------------------------------------------- estimate and checks
def made_moments(plan: PlanDoc) -> list[Moment]:
    return [m for m in plan.moments if m.medium == "made"]


def estimate(plan: PlanDoc) -> Estimate:
    made = made_moments(plan)
    todo = [m for m in made if not m.media]                       # a picture that already exists costs nothing again
    gpu = len(todo) * plan.still_seconds
    lines = [Line(label="Listening", count=0, seconds=0.0, where="done"),
             Line(label="Made for you", count=len(todo), seconds=round(gpu, 1), where="on the picture server" if todo else ""),
             Line(label="Same picture again", count=sum(1 for m in plan.moments if m.medium == "repeat")),
             Line(label="Word cards", count=sum(1 for m in plan.moments if m.medium == "card")),
             Line(label="Putting it together and sound", count=len(plan.moments), seconds=round(ASSEMBLE_BASE + ASSEMBLE_PER_MOMENT * len(plan.moments), 1))]
    total = sum(x.seconds for x in lines)
    return Estimate(lines=lines, total_seconds=round(total, 1), made=len(made), gpu_seconds=round(gpu, 1))


def is_expensive(plan: PlanDoc) -> bool:
    return len([m for m in made_moments(plan) if not m.media]) >= EXPENSIVE_MOMENTS


def checks(plan: PlanDoc) -> list[str]:
    """Gentle notes, never blockers: the person is the editor. Each one says what to look at in a sentence."""
    out: list[str] = []
    ms = plan.moments
    if not ms:
        return ["The plan has no moments."]
    if ms[0].beat.time - ms[0].start > 1.5:
        out.append("The first change is late: something should happen in the first second and a half.")
    for m in ms:
        if m.seconds > 3.2 and not m.locked:
            out.append(f"Moment {m.id[1:]} holds one picture for {m.seconds:.1f} s: viewers look away after about three.")
    lens = [round(m.seconds, 1) for m in ms]
    for a, b in zip(ms, ms[1:]):
        if abs(a.seconds - b.seconds) < 0.15 and len(ms) > 4:
            out.append(f"Moments {a.id[1:]} and {b.id[1:]} are almost the same length; the rhythm feels mechanical.")
            break
    if len(set(lens)) < max(2, len(lens) // 3) and len(ms) > 5:
        out.append("The lengths hardly vary; varied lengths keep people watching.")
    for m in ms:
        bad = ungrounded(plan, m)
        if bad:
            out.append(f"Moment {m.id[1:]}: “{bad}” is not in what is said. You can keep it, but the picture may not match the speech.")
    return out


def ungrounded(plan: PlanDoc, m: Moment) -> str:
    """The first number or longer word in the moment's picture text that the speech never says ('' when it all comes from the speech)."""
    have = {_norm(w.text) for x in plan.moments for w in x.words}
    for t in re.findall(r"[\w$%]+", m.draw.casefold()):
        if (t.isdigit() or len(t) > 5) and _norm(t) not in have and not _common(t):
            return t
    return ""


_COMMON = set("""person people someone something nothing everything background simple clean cartoon drawing picture illustration figure dramatic lighting vertical
composition standing sitting looking holding walking hands behind through between against around outside inside beside""".split())


def _common(t: str) -> bool:
    return t in _COMMON or t.endswith(("ing", "ed", "ly"))


# ----------------------------------------------------------------------------- editing
OPS = ("set_medium", "set_beat", "set_prompt", "choose_alternative", "lock", "unlock", "merge", "split", "set_style", "set_goal", "set_pace", "set_budget", "set_idea",
       "set_place", "set_moment_place", "set_cast")


def apply_edit(plan: PlanDoc, op: dict[str, Any], project=None) -> list[str]:
    """Do one typed operation on `plan` in place. Returns the notes the person should see ("Moment 4 now keeps the picture before it"). Raises PlanError with a sentence on a bad edit.

    A locked moment refuses changes except `unlock`; structural edits (merge, split, pace) keep the moments they do not touch, with their edits and locks.
    """
    kind = op.get("op")
    if kind not in OPS:
        raise PlanError(f"'{kind}' is not something a plan can do")
    notes: list[str] = []
    if plan.state in ("running", "done"):
        raise PlanError("The video is already being made. Edit the moments that have not started in the editor, or make it again.")

    def free(m: Moment) -> Moment:
        if m.locked:
            raise PlanError(f"Moment {m.id[1:]} is locked. Unlock it to change it.")
        return m

    if kind == "set_medium":
        m = free(plan.moment(str(op.get("moment"))))
        to = str(op.get("medium"))
        if to not in MEDIA:
            raise PlanError(f"'{to}' is not one of: made for you, same picture again, word card")
        if to == "repeat" and plan.moments.index(m) == 0:
            raise PlanError("The first moment has no picture before it to repeat.")
        m.medium, m.media, m.status = to, ("" if to != "made" else m.media), "planned"
        m.alternatives = _alts(to, m)
        notes.append(f"Moment {m.id[1:]}: {MEDIUM_LABEL[to].lower()}.")
    elif kind == "choose_alternative":
        m = free(plan.moment(str(op.get("moment"))))
        alt = next((a for a in m.alternatives if a.medium == op.get("medium")), None)
        if not alt:
            raise PlanError("That idea is not on offer for this moment.")
        m.medium, m.media, m.status = alt.medium, "", "planned"                        # type: ignore[assignment]
        m.alternatives = _alts(m.medium, m)
        notes.append(f"Moment {m.id[1:]}: {MEDIUM_LABEL[m.medium].lower()}.")
    elif kind == "set_prompt":
        m = free(plan.moment(str(op.get("moment"))))
        text = str(op.get("text", "")).strip()
        if not text:
            raise PlanError("Say what the picture should show.")
        if len(text) > 300:
            raise PlanError("That is too long for one picture. Keep it under 300 characters.")
        m.draw, m.media, m.status = text, "", "planned"
        bad = ungrounded(plan, m)
        if bad:
            notes.append(f"Moment {m.id[1:]}: “{bad}” is not in what is said. It is yours to keep; the picture may not match the speech.")
    elif kind == "set_beat":
        m = free(plan.moment(str(op.get("moment"))))
        ref = next((w for w in m.words if w.id == op.get("word")), None)
        if not ref:
            raise PlanError("That word is not in this moment.")
        t = _word_time(project, ref.id) if project is not None else m.beat.time
        m.beat = BeatRef(word_id=ref.id, time=round(t, 2), kind="emphasis", strength=max(ref.stress, 0.6), why=f"You chose “{ref.text}” as the word the picture changes on.")
        for w in m.words:
            w.stress = 1.0 if w.id == ref.id else min(w.stress, 0.6)
        notes.append(f"Moment {m.id[1:]} now changes on “{ref.text}”.")
    elif kind in ("lock", "unlock"):
        plan.moment(str(op.get("moment"))).locked = kind == "lock"
    elif kind == "merge":
        i = _index(plan, op.get("moment"))
        if i >= len(plan.moments) - 1:
            raise PlanError("There is nothing after this moment to join it with.")
        a, b = free(plan.moments[i]), free(plan.moments[i + 1])
        a.end, a.sentence_ids, a.text = b.end, a.sentence_ids + b.sentence_ids, f"{a.text} {b.text}"
        a.words += b.words
        a.media, a.status = "", "planned"
        del plan.moments[i + 1]
        _renumber(plan)
        notes.append(f"Joined two moments into moment {a.id[1:]}.")
    elif kind == "split":
        i = _index(plan, op.get("moment"))
        m = free(plan.moments[i])
        sid = str(op.get("sentence", ""))
        if sid not in m.sentence_ids[1:]:
            raise PlanError("Choose where in this moment the picture should change: at the start of one of its later sentences.")
        k = m.sentence_ids.index(sid)
        if project is None:
            raise PlanError("Splitting needs the project's words.")
        beats = {b.id: b for b in project.beats().beats}
        words = project.transcript().by_id()
        at = beats[sid].start
        left_words = [w for w in m.words if (words.get(w.id) is not None and words[w.id].start < at)]
        right_words = m.words[len(left_words):]
        if not left_words or not right_words:
            raise PlanError("Both parts need some words.")
        second = m.model_copy(deep=True)
        m.end, m.sentence_ids, m.words = round(at, 2), m.sentence_ids[:k], left_words
        m.text = " ".join(beats[s].text for s in m.sentence_ids)
        second.start, second.sentence_ids, second.words = round(at, 2), second.sentence_ids[k:], right_words
        second.text, second.card, second.media, second.status, second.locked = " ".join(beats[s].text for s in second.sentence_ids), "", "", "planned", False
        second.draw = beats[sid].text[:120]
        second.beat = BeatRef(word_id=right_words[0].id, time=round(words[right_words[0].id].start, 2), kind="first", strength=0.3, why="Nothing stands out, so the picture changes as it begins.")
        m.media, m.status = "", "planned"
        plan.moments.insert(i + 1, second)
        _renumber(plan)
        notes.append(f"Moment {m.id[1:]} became two: a new picture where “{beats[sid].text[:30]}…” begins.")
    elif kind == "set_style":
        from ..reel.style import FIGURE, STYLES

        st = str(op.get("value"))
        if st not in STYLES:
            raise PlanError(f"'{st}' is not a look: choose one of {', '.join(STYLES)}")
        plan.idea.style = st
        if not plan.idea.character or plan.idea.character in FIGURE.values():
            plan.idea.character = FIGURE.get(st, "")
        n = 0
        for m in plan.moments:
            if not m.locked and m.medium == "made" and m.media:
                m.media, m.status, n = "", "planned", n + 1
        notes.append(f"The look is now {STYLES[st]['label'].lower()}." + (f" {n} picture{'s' if n != 1 else ''} will be drawn again." if n else ""))
    elif kind == "set_goal":
        plan.idea.goal = str(op.get("text", "")).strip()[:300]
    elif kind == "set_place":                     # define or change a place; every moment in it is drawn again
        name, text = str(op.get("name", "")).strip()[:40], str(op.get("text", "")).strip()
        if not name:
            raise PlanError("Give the place a short name.")
        if len(text) > 240:
            raise PlanError("Describe the place in under 240 characters.")
        if text:
            plan.idea.places[name] = text
        else:
            plan.idea.places.pop(name, None)
        for m in plan.moments:
            if m.place == name:
                if not text:
                    m.place = ""
                if not m.locked:
                    m.media, m.status = "", "planned"
        notes.append(f"Place “{name}” {'set' if text else 'removed'}.")
    elif kind == "set_cast":                      # a person's look; every moment that names them is drawn again
        name, text = str(op.get("name", "")).strip()[:30], str(op.get("text", "")).strip()
        if not name:
            raise PlanError("Give the person a name.")
        if len(text) > 160:
            raise PlanError("Describe the person in under 160 characters.")
        if text:
            plan.idea.cast[name] = text
        else:
            plan.idea.cast.pop(name, None)
        for m in plan.moments:
            if not m.locked and re.search(rf"\b{re.escape(name)}\b", m.draw, re.I):
                m.media, m.status = "", "planned"
        notes.append(f"{name} {'looks like this now' if text else 'has no description now'}.")
    elif kind == "set_moment_place":
        m = free(plan.moment(str(op.get("moment"))))
        name = str(op.get("place", "")).strip()
        if name and name not in plan.idea.places:
            raise PlanError(f"There is no place “{name}”. Add it first (set_place).")
        m.place, m.media, m.status = name, "", "planned"
        notes.append(f"Moment {m.id[1:]} happens in {name or 'no named place'}.")
    elif kind == "set_idea":
        field = str(op.get("field"))
        if field not in ("audience", "tone", "character"):
            raise PlanError("That part of the idea cannot be changed here.")
        setattr(plan.idea, field, str(op.get("value", "")).strip()[:200])
        if field == "character":
            for m in plan.moments:
                if not m.locked and m.media:
                    m.media, m.status = "", "planned"
    elif kind == "set_pace":
        pace = str(op.get("value"))
        if pace not in PACE:
            raise PlanError("Pace is punchy, balanced or calm.")
        if project is None:
            raise PlanError("Changing the pace needs the project's words.")
        keep = {tuple(m.sentence_ids): m for m in plan.moments}
        reading = _reading(project)
        words = project.transcript().by_id()
        fresh = [_moment_from_slot(s, words, plan.idea.style, plan.idea.character) for s in _slots(project.beats().beats, reading, pace)]
        locked = [m for m in plan.moments if m.locked]
        if locked:
            raise PlanError("Some moments are locked, so the pace cannot change. Unlock them first.")
        plan.moments = [keep.get(tuple(m.sentence_ids), m) for m in fresh]
        plan.idea.pace = pace                                                   # type: ignore[assignment]
        notes.append(f"{len(plan.moments)} moments at a {pace} pace.")
    elif kind == "set_budget":
        n = op.get("n")
        plan.budget.n_generated = None if n is None else int(n)
        notes += apply_budget(plan)
    plan.rev += 1
    plan.notes = [n for n in plan.notes if not n.startswith("•")]
    return notes


def _alts(medium: str, m: "Moment") -> list[Alt]:
    """The other two ways to show this moment, with a reason each: always the ones it is not using now."""
    return [Alt(medium=x, why=ALT_WHY[x]) for x in MEDIA if x != medium]


def _reading(project):
    from ..reel.plan import READING
    from ..reel.reading import Reading

    raw = read_json(project.dir / READING, None)
    if not raw:
        raise PlanError("The script has not been read yet.")
    return Reading.model_validate(raw)


def _word_time(project, word_id: str) -> float:
    w = project.transcript().by_id().get(word_id)
    return float(w.start) if w is not None else 0.0


def _index(plan: PlanDoc, mid: Any) -> int:
    for i, m in enumerate(plan.moments):
        if m.id == mid:
            return i
    raise PlanError(f"there is no moment '{mid}'")


def _renumber(plan: PlanDoc) -> None:
    for i, m in enumerate(plan.moments, 1):
        m.id = f"s{i}"


def priority(m: Moment, index: int) -> float:
    """How much a moment deserves its own made picture when the number is limited: the opening, a new point, a chapter label, a number, a strong word."""
    return (3.0 if index == 0 else 0.0) + (2.0 if m.turn else 0.0) + (1.5 if m.card else 0.0) + (1.0 if re.search(r"\d", m.draw) else 0.0) + m.beat.strength + min(1.0, m.seconds / 3.0)


def apply_budget(plan: PlanDoc) -> list[str]:
    """Keep the n most deserving moments as 'made for you'; the others keep the picture before them. Locked and already-made moments are left alone."""
    n = plan.budget.n_generated
    if n is None:
        return []
    made = [(i, m) for i, m in enumerate(plan.moments) if m.medium == "made"]
    keep = {m.id for m in plan.moments if m.locked and m.medium == "made"}
    rest = sorted((x for x in made if x[1].id not in keep), key=lambda x: -priority(x[1], x[0]))
    room = max(0, n - len(keep))
    chosen = keep | {m.id for _, m in rest[:room]}
    changed = 0
    for i, m in made:
        if m.id not in chosen and not m.locked and i > 0:
            m.medium, m.media, m.status = "repeat", "", "planned"
            changed += 1
    out = []
    if changed:
        out.append(f"{changed} moment{'s' if changed != 1 else ''} will keep the picture before {'them' if changed != 1 else 'it'} to stay within {n} made for you.")
    if n < 1 + len(keep):
        out.append("The first moment always keeps its own picture.")
    return out


# ----------------------------------------------------------------------------- the review gate
def review_wanted(plan: PlanDoc, setting: str, project_choice: str = "auto") -> bool:
    """Should the person see this plan before it is made? `project_choice` ('auto'|'always'|'never') beats the setting ('always'|'when_expensive'|'never')."""
    choice = project_choice if project_choice in ("always", "never") else setting
    if choice == "never":
        return False
    if choice == "always":
        return True
    return is_expensive(plan)


def signature(plan: PlanDoc) -> str:
    """Changes when what would be made changes (used to know that an approved plan still matches the words)."""
    key = [(m.id, m.sentence_ids, m.medium, m.draw, m.card) for m in plan.moments] + [plan.idea.style, plan.idea.character]
    return hashlib.sha1(repr(key).encode()).hexdigest()[:12]


def matches(plan: PlanDoc, beat_ids: list[str]) -> bool:
    """The plan still covers exactly these sentences, in order (the speech has not been recognised again since)."""
    flat = [s for m in plan.moments for s in m.sentence_ids]
    return flat == list(beat_ids)
