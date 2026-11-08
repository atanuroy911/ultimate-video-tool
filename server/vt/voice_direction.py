"""Voice direction and vocal events: how a sentence should be delivered, in one vocabulary of ours, translated for each voice engine.

Two things a director (a person writing a script, or the AI) can ask for, per sentence:

* **Direction**: a free-text instruction for the delivery ("slowly, with a restrained, serious tone"; "whispering"; "out of breath"). In a script it is written
  at the start of a sentence in curly braces: `{slowly, serious} Never put your name on the account.`
* **Vocal events**: sounds that are not words: `(laugh)`, `(sigh)`, `(cough)`, `(clears throat)` and `(breath)`, anywhere in a sentence. The Chinese forms
  `[笑] [咳嗽] [清嗓子] [叹气]` and OmniVoice's `[laughter]` / `[sigh]` are understood too.

Our vocabulary is the same for every engine. Each engine speaks its own dialect (Breeze TTS 2 wants `(laugh)` and a free instruction, OmniVoice wants
`[laughter]` and accepts only `whisper` as a style, Edge and Kokoro understand neither). `render()` turns one parsed sentence
into what a given dialect can use and says what it had to drop, so a person is never told an engine did something it could not.

The captions and word timings are built from `Direction.text`: the words only, never the notes and the sound tags.
See docs/plans/PLAN-VOICE-DIRECTION.MD.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

EVENTS = ("laugh", "sigh", "cough", "clears throat", "breath")
_ALIASES = {
    "laugh": "laugh", "laughs": "laugh", "laughing": "laugh", "laughter": "laugh", "chuckle": "laugh", "chuckles": "laugh", "笑": "laugh",
    "sigh": "sigh", "sighs": "sigh", "sighing": "sigh", "叹气": "sigh",
    "cough": "cough", "coughs": "cough", "coughing": "cough", "咳嗽": "cough",
    "clears throat": "clears throat", "clear throat": "clears throat", "clearing throat": "clears throat", "throat clear": "clears throat", "清嗓子": "clears throat",
    "breath": "breath", "breathe": "breath", "breathes": "breath", "inhale": "breath", "gasp": "breath",
}
_NOTE = re.compile(r"^\s*\{([^{}]{2,200})\}\s*")
_PAREN = re.compile(r"\(\s*([A-Za-z][A-Za-z ]{2,18}?)\s*\)")
_BRACKET = re.compile(r"\[\s*([A-Za-z一-鿿][A-Za-z 一-鿿]{0,18}?)\s*\]")

# Each dialect: how events are written, and what an instruction may be. instruction: "free" | "whisper" | "none"
DIALECTS: dict[str, dict] = {
    "breeze": {"events": {"laugh": "(laugh)", "sigh": "(sigh)", "cough": "(cough)", "clears throat": "(clears throat)"}, "instruction": "free", "label": "Breeze TTS 2"},
    "omnivoice": {"events": {"laugh": "[laughter]", "sigh": "[sigh]"}, "instruction": "whisper", "label": "OmniVoice"},
    "none": {"events": {}, "instruction": "none", "label": "a voice without direction (Edge, Kokoro, MMS)"},
}


@dataclass
class Direction:
    text: str                                              # the words only: what the captions and the word timings are made from
    instruction: str = ""
    parts: list[tuple[str, str]] = field(default_factory=list)   # ("text", words) or ("event", canonical name), in order

    @property
    def events(self) -> list[str]:
        return [v for k, v in self.parts if k == "event"]


@dataclass
class Rendered:
    spoken: str                                            # what to send to the engine
    instruction: str                                       # "" when the engine takes none
    rate: float                                            # a speed factor derived from the instruction when the engine cannot follow it
    dropped: list[str] = field(default_factory=list)       # what this engine could not do, in words


def _canon(name: str) -> Optional[str]:
    return _ALIASES.get(re.sub(r"\s+", " ", name.strip().lower()))


def parse(raw: str) -> Direction:
    """Split one script sentence into its words, its direction note and its vocal events."""
    instruction = ""
    m = _NOTE.match(raw)
    if m:
        instruction = re.sub(r"\s+", " ", m.group(1)).strip()
        raw = raw[m.end():]
    marks: list[tuple[int, int, str]] = []
    for rx in (_PAREN, _BRACKET):
        for e in rx.finditer(raw):
            canon = _canon(e.group(1))
            if canon:                                       # any other bracket or parenthesis is ordinary text and stays
                marks.append((e.start(), e.end(), canon))
    marks.sort()
    parts: list[tuple[str, str]] = []
    pos = 0
    for a, b, name in marks:
        if a < pos:
            continue
        if raw[pos:a].strip():
            parts.append(("text", raw[pos:a]))
        parts.append(("event", name))
        pos = b
    if raw[pos:].strip() or not parts:
        parts.append(("text", raw[pos:]))
    text = re.sub(r"\s+", " ", " ".join(v for k, v in parts if k == "text")).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return Direction(text=text, instruction=instruction, parts=parts)


_SLOW = re.compile(r"\b(slow|slowly|calm|measured|deliberate|restrained|hesitant|thoughtful)\b", re.I)
_FAST = re.compile(r"\b(fast|quick|quickly|rapid|rushed|energetic|excited|urgent|out of breath|brisk)\b", re.I)


def pace_from(instruction: str) -> float:
    """A speed factor from the words of a direction: the one part of it every engine can follow, because speed is a setting everywhere."""
    if not instruction:
        return 1.0
    slow, fast = bool(_SLOW.search(instruction)), bool(_FAST.search(instruction))
    return 0.9 if slow and not fast else 1.1 if fast and not slow else 1.0


def render(d: Direction, dialect: str = "none", *, direction_on: bool = True, text_fn=None) -> Rendered:
    """What an engine of this dialect gets for this sentence. Events it cannot make are dropped and named; an instruction it cannot follow becomes a speed change."""
    spec = DIALECTS.get(dialect, DIALECTS["none"])
    out: list[str] = []
    dropped: list[str] = []
    for kind, value in d.parts:
        if kind == "text":
            out.append((text_fn(value) if text_fn else value).strip())
        elif direction_on and value in spec["events"]:
            out.append(spec["events"][value])
        else:
            dropped.append(f"({value}) is not something {spec['label']} can do")
    spoken = re.sub(r"\s+([,.;:!?।])", r"\1", re.sub(r"\s+", " ", " ".join(x for x in out if x)).strip())
    instruction, rate = "", 1.0
    if d.instruction and direction_on:
        mode = spec["instruction"]
        if mode == "free":
            instruction = d.instruction
        elif mode == "whisper":
            if re.search(r"\bwhisper", d.instruction, re.I):
                instruction = "whisper"
            if instruction != d.instruction.strip().lower():
                rate = pace_from(d.instruction)
                dropped.append(f"{spec['label']} follows only 'whisper'; the rest of the direction became a speed change" if rate != 1.0 else f"{spec['label']} follows only 'whisper'")
        else:
            rate = pace_from(d.instruction)
            dropped.append(f"{spec['label']} cannot follow a direction; it was used as a speed change" if rate != 1.0 else f"{spec['label']} cannot follow a direction")
    return Rendered(spoken=spoken, instruction=instruction, rate=rate, dropped=dropped)


def strip(raw: str) -> str:
    """The words only (what the captions are made from)."""
    return parse(raw).text


# ------------------------------------------------------------------------------------------------------------------------------ the director's suggestions
SYSTEM = (
    "You direct the voice of a narrator reading a short video script. For some sentences you say HOW they should be delivered, in a short free-text instruction "
    "(for example 'slowly, with a restrained, serious tone', 'warm and amused', 'urgent, a little out of breath', 'whispering'), written in the language of the script. "
    "You may also place a vocal event before or after a sentence: laugh, sigh, cough, clears throat or breath, at most one event for every six sentences, and only where a person would really make it. "
    "You never change, add or remove a word. Leave most sentences plain: a delivery note is for a change of mood, a hook, a turn, a punchline or a serious point."
)
SCHEMA: dict = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "instruction": {"type": "string"}, "before": {"type": "string", "enum": ["", *EVENTS]}, "after": {"type": "string", "enum": ["", *EVENTS]}},
    "required": ["i"]}}}, "required": ["items"]}


def rules_suggest(sentences: list[str]) -> dict[int, dict]:
    """Without an AI: only what punctuation says. Never an event (a laugh is never invented by a rule)."""
    out: dict[int, dict] = {}
    for i, s in enumerate(sentences):
        s = s.strip()
        if s.endswith("!") and len(s.split()) <= 12:
            out[i] = {"instruction": "energetic and emphatic"}
        elif s.endswith(("...", "\u2026")):
            out[i] = {"instruction": "slow and thoughtful"}
    return out


def suggest(sentences: list[str], language: str = "en", *, use_ai: bool = True, provider=None, events: tuple[str, ...] = EVENTS) -> dict[int, dict]:
    """{sentence index: {"instruction", "before", "after"}} for the sentences the director wants delivered in a particular way. Sentences with their own note are skipped by the caller."""
    base = rules_suggest(sentences)
    if not use_ai or not sentences:
        return base
    try:
        from .ai import complete_json
        from .ai.providers import ai_enabled
    except Exception:                                                              # noqa: BLE001
        return base
    if provider is None and not ai_enabled():
        return base
    numbered = "\n".join(f"{i}: {s}" for i, s in enumerate(sentences))
    allowed = ", ".join(events) if events else "none (this voice cannot make sounds: give no events)"
    try:
        data = complete_json(f"Script language: {language}. Sounds this voice can make: {allowed}. Sentences, numbered:\n{numbered}\n\nGive delivery notes for the sentences that need one.", SCHEMA, system=SYSTEM, provider=provider,
                             retries=1, max_tokens=2500, temperature=0.3,
                             check=lambda d: [f"sentence {x.get('i')} does not exist" for x in d.get("items", []) if not isinstance(x.get("i"), int) or not 0 <= x["i"] < len(sentences)])
    except Exception:                                                              # noqa: BLE001 - a missing or confused model leaves the rules' notes; the voice never waits on it
        return base
    out = dict(base)
    events_left = max(1, len(sentences) // 6)
    for x in data.get("items", []):
        note = {k: x[k] for k in ("instruction", "before", "after") if x.get(k) and (k == "instruction" or x[k] in events)}
        for k in ("before", "after"):
            if k in note:
                if events_left <= 0:
                    note.pop(k)
                else:
                    events_left -= 1
        if note:
            out[x["i"]] = note
    return out
