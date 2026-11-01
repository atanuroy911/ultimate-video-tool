"""Read a script the way a director would, before any picture is chosen.

What the reels the owner supplied have in common is in what they *say* (docs/research/REELS-ANALYSIS.md section 5): a hook that opens a loop,
a shape (claim, stakes, mechanism, twist, payoff), concrete things a picture can show, and turns ("but", "step 2", "Day 26"). The reading
finds those, from the words only, so the pace, the medium and the picture for each sentence follow from the content instead of from a setting.

`read_script` asks the AI first (one call per window of sentences) and falls back to rules, so a missing model never stops a video. The AI is
told to describe only what a sentence says; `check` rejects a picture description that brings in a number or a name the sentence does not contain.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field

KINDS = ("steps", "story", "explanation", "argument", "list", "opinion")
STYLES = ("cartoon", "line-art", "comic", "photo")
WINDOW = 14                                          # sentences per AI call

STOP = set("""a an the and or but so if then than that this these those it its is are was were be been being am do does did have has had
i you he she we they me him her us them my your his our their to of in on at by for with from as into over under about after before up down out off
not no yes can could will would should may might must just very more most much many some any all each every own same too also only even still
there here when where what which who whom whose why how now one two three""".split())
NUMBER = re.compile(r"[$€£৳]?\d[\d,.]*\s?(?:%|percent|k|m|million|billion|days?|hours?|minutes?|seconds?|years?|months?|weeks?|dollars?)?", re.I)
JUMP = re.compile(r"^\W*(step|day|rule|tip|number|lesson|part|chapter|reason|secret|week|month)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", re.I)


class Hook(BaseModel):
    text: str = ""
    type: str = Field(default="other", description="question, claim, prohibition, story or other")
    strength: float = Field(default=0.0, ge=0, le=1)


class BeatNote(BaseModel):
    beat: str
    draw: str = Field(default="", description="what one picture should show for this sentence, in plain English, using only things the sentence says")
    emphasis: str = Field(default="", description="the one word of the sentence that carries it, copied exactly")
    turn: bool = Field(default=False, description="the sentence opens a new point: but, now, here is the secret, a question, a new step")


class Jump(BaseModel):
    beat: str
    label: str


class Reading(BaseModel):
    kind: str = "explanation"
    style: str = "cartoon"
    style_why: str = ""
    character: str = Field(default="", description="a generic recurring figure for a story or steps video, never a real person")
    hook: Hook = Field(default_factory=Hook)
    jumps: list[Jump] = Field(default_factory=list)
    notes: list[BeatNote] = Field(default_factory=list)
    source: str = "rules"
    warnings: list[str] = Field(default_factory=list)

    def note(self, beat_id: str) -> Optional[BeatNote]:
        return next((n for n in self.notes if n.beat == beat_id), None)


def _words(text: str) -> list[str]:
    return re.findall(r"[\w$%'’.,-]+", text, flags=re.UNICODE)


def _content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[^\W\d_][\w'’-]*", text, flags=re.UNICODE) if w.lower() not in STOP and len(w) > 2]


def rules_kind(texts: list[str]) -> str:
    joined = " ".join(texts)
    steps = sum(1 for t in texts if JUMP.match(t) and JUMP.match(t).group(1).lower() in ("step", "tip", "rule", "lesson", "reason", "secret", "number"))
    days = sum(1 for t in texts if JUMP.match(t) and JUMP.match(t).group(1).lower() in ("day", "week", "month", "chapter", "part"))
    if steps >= 2:
        return "steps"
    if days >= 2 or re.search(r"\b(once upon|one day|he said|she said|he walked|she walked|then he|then she)\b", joined, re.I):
        return "story"
    if len(re.findall(r"\b(vs\.?|versus|but|however|instead|myth)\b", joined, re.I)) >= 4 and not re.search(r"\byou\b", joined, re.I):
        return "argument"
    if len(re.findall(r"\b(first|second|third|number \d|\d\.)\b", joined, re.I)) >= 3:
        return "list"
    return "explanation"


def rules_hook(first: str) -> Hook:
    s = first.strip()
    if not s:
        return Hook()
    kind, strength = "other", 0.3
    if s.endswith("?") or re.match(r"^(how|why|what|did you|do you|have you|can you|is it|are you)\b", s, re.I):
        kind, strength = "question", 0.6
    elif re.match(r"^(never|don't|do not|stop|quit|avoid)\b", s, re.I):
        kind, strength = "prohibition", 0.7
    elif re.search(r"\b(secret|nobody|no one|most people|they don't|truth|actually|can save|will change|\d+)\b", s, re.I):
        kind, strength = "claim", 0.6
    elif re.match(r"^(hello|hi|hey|welcome|today|in this video|so today)\b", s, re.I):
        kind, strength = "other", 0.1
    return Hook(text=s[:160], type=kind, strength=strength)


def rules_style(kind: str, texts: list[str]) -> tuple[str, str]:
    joined = " ".join(texts).lower()
    if kind == "story":
        return "comic", "a story reads best as drawn scenes of one world"
    if re.search(r"\b(stress|brain|heart|body|hormone|health|science|cortisol)\b", joined):
        return "line-art", "a science explanation reads best as calm line drawings, one idea per picture"
    if kind in ("steps", "argument", "list"):
        return "cartoon", "steps and arguments read best as clean cartoon objects with a clear subject"
    return "cartoon", "a clear, friendly default"


def rules_notes(beats: list[Any]) -> list[BeatNote]:
    notes = []
    for b in beats:
        text = b.text
        nums = [m.group(0).strip() for m in NUMBER.finditer(text) if re.search(r"\d", m.group(0))]
        content = _content_words(text)
        emph = nums[0] if nums else (max(content, key=len) if content else "")
        thing = ", ".join(dict.fromkeys(content[:4])) or text[:60]
        notes.append(BeatNote(beat=b.id, draw=f"a simple picture of {thing}" + (f" with the number {nums[0]}" if nums else ""), emphasis=emph,
                              turn=bool(re.match(r"^\W*(but|now|so|here|and then|however|is it|why|what)\b", text, re.I))))
    return notes


def rules_reading(beats: list[Any]) -> Reading:
    texts = [b.text for b in beats]
    kind = rules_kind(texts)
    style, why = rules_style(kind, texts)
    jumps = [Jump(beat=b.id, label=re.sub(r"\s+", " ", b.text.strip().rstrip(".:!"))[:28].upper()) for b in beats if JUMP.match(b.text) and len(b.text.split()) <= 6]
    return Reading(kind=kind, style=style, style_why=why, hook=rules_hook(texts[0] if texts else ""), jumps=jumps, notes=rules_notes(beats), source="rules")


# ------------------------------------------------------------------------------------------------------------------------------------- the AI
SYSTEM = (
    "You are the director of a short vertical video made from a spoken script. You read the script and decide what one picture should show for each "
    "sentence. You describe ONLY what the sentence says: never add a number, a name, a place or a claim that is not in it. Pictures show concrete things "
    "(a calculator for '20 percent', a bank for 'mortgage', a clock for 'time'). Write in plain English even if the script is in another language. "
    "Never describe a real person's face or likeness; use a generic figure. Draw SCENES, not icons: for each sentence describe one scene in which the recurring "
    "figure does or shows what the sentence says, with the setting and the key object, for example 'the figure in a beige coat holds up a big check for 200,000 "
    "dollars in front of a small brick apartment building'. Vary the setting and the camera (close, wide, from above) from one sentence to the next."
)
SCHEMA: dict = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "style": {"type": "string", "enum": list(STYLES)},
        "style_why": {"type": "string"},
        "character": {"type": "string"},
        "hook_type": {"type": "string", "enum": ["question", "claim", "prohibition", "story", "other"]},
        "hook_strength": {"type": "number"},
        "notes": {"type": "array", "items": {"type": "object", "properties": {
            "beat": {"type": "string"}, "draw": {"type": "string"}, "emphasis": {"type": "string"}, "turn": {"type": "boolean"}}, "required": ["beat", "draw", "emphasis", "turn"]}},
    },
    "required": ["kind", "style", "notes"],
}


def _prompt(window: list[Any], first: bool, kind_hint: str) -> str:
    lines = "\n".join(f'{b.id}: "{b.text}"' for b in window)
    head = (
        "Read these numbered sentences of a script. Decide the kind of video (steps, story, explanation, argument, list or opinion), a drawing style "
        "(cartoon: clean flat cartoon objects; line-art: calm pencil line drawings; comic: inked scenes of one world; photo: cinematic photographs), "
        "and ALWAYS a short generic description of ONE recurring figure who appears in the pictures (age, clothes, hair; no real person; for a science or health topic a simple stick-like person is fine). Rate how strong the first sentence "
        "is as a hook (0 to 1) and name its type.\n" if first else
        f"This continues the same script (kind so far: {kind_hint}). Only fill the notes.\n")
    return (head + "For EVERY sentence give: `draw` (one concrete scene with the figure, at most 35 words, only things the sentence says), `emphasis` (the single word of the sentence "
            "that carries it, copied exactly as written), and `turn` (true if the sentence opens a new point: but, now, here is the secret, a question, a new step).\n\n" + lines)


def _check(data: dict, window: list[Any]) -> list[str]:
    errs: list[str] = []
    by = {b.id: b for b in window}
    seen = {n.get("beat") for n in data.get("notes", [])}
    missing = [b.id for b in window if b.id not in seen]
    if missing:
        errs.append(f"no note for sentences {', '.join(missing[:6])}")
    for n in data.get("notes", []):
        b = by.get(n.get("beat"))
        if b is None:
            errs.append(f"unknown sentence id {n.get('beat')}")
            continue
        said = set(re.findall(r"\d[\d,.]*", b.text))
        for num in re.findall(r"\d[\d,.]*", n.get("draw", "")):
            if num not in said and num.rstrip(".,") not in {s.rstrip(".,") for s in said}:
                errs.append(f"{n['beat']}: the picture mentions the number {num}, which the sentence does not say")
    return errs


def read_script(beats: list[Any], *, provider=None, use_ai: bool = True) -> Reading:
    """The AI's reading where it answers and passes the check, the rules' reading for everything else."""
    base = rules_reading(beats)
    if not use_ai or not beats:
        return base
    try:
        from ..ai import complete_json
        from ..ai.providers import ai_enabled
    except Exception:
        return base
    if provider is None and not ai_enabled():
        base.warnings.append("no AI is set up: the pictures were chosen by rules")
        return base
    notes: dict[str, BeatNote] = {n.beat: n for n in base.notes}
    ok = 0
    first = True
    for start in range(0, len(beats), WINDOW):
        window = beats[start:start + WINDOW]
        try:
            data = complete_json(_prompt(window, first, base.kind), SCHEMA, system=SYSTEM, provider=provider, retries=1, max_tokens=3500, temperature=0.2,
                                 check=lambda d, w=window: _check(d, w))
        except Exception as e:
            base.warnings.append(f"AI window {start // WINDOW + 1} skipped ({type(e).__name__}); the rules chose those pictures")
            first = first and start == 0
            continue
        ok += 1
        if first:
            first = False
            base.kind = data.get("kind", base.kind)
            base.style, base.style_why = data.get("style", base.style), data.get("style_why", base.style_why)
            base.character = (data.get("character") or "")[:160]
            base.hook = Hook(text=beats[0].text[:160], type=data.get("hook_type", base.hook.type), strength=max(0.0, min(1.0, float(data.get("hook_strength", base.hook.strength)))))
        for n in data.get("notes", []):
            if n.get("beat") in {b.id for b in window}:
                words = {w.lower() for w in _words(next(b.text for b in window if b.id == n["beat"]))}
                emph = n.get("emphasis", "")
                if emph and emph.lower().strip(".,!?") not in {w.strip(".,!?") for w in words}:
                    emph = notes[n["beat"]].emphasis                                        # a word the sentence does not contain: keep the rules' word
                notes[n["beat"]] = BeatNote(beat=n["beat"], draw=n.get("draw", "")[:300] or notes[n["beat"]].draw, emphasis=emph, turn=bool(n.get("turn")))
    base.notes = [notes[b.id] for b in beats]
    if len(base.jumps) >= 2 and base.kind not in ("steps", "story"):          # numbered turns ("Step one", "Day 26") are what steps and stories are: the words decide, not the model
        base.kind = rules_kind([b.text for b in beats])
    if ok:
        base.source = "ai"
    return base
