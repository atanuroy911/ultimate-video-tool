"""The one big, versioned prompt that asks any AI for a Video Script. Parts are functions so each can be tested; the catalogue is generated from code."""
from __future__ import annotations

import json
from typing import Optional

from ..planner.catalogue import component_catalogue
from ..schema import Beats, Transcript
from . import catalogue as C
from .models import VERSION

PROMPT_VERSION = "1." + VERSION

ROLE = """You are the director and animator of a short {kind_text} video. A speaker's words are already recorded and timed. Your job is to decide what
appears on screen and when, as a Video Script in JSON. Captions and the voice are automatic; you never write captions."""

KIND_TEXT = {"stick": "stick-figure animated", "emoji": "emoji-told", "explainer": "faceless motion-graphics explainer", "infographic": "infographic", "cartoon": "cartoon",
             "mixed": "mixed-style"}

CRAFT_RULES = """\
CRAFT RULES (follow all of them)
Staging
- One main action at a time. The character who speaks or acts is the focus; others idle.
- The speaker faces the audience. Entrances come from the side the character will face; keep the same character on the same side of the screen.
- Props persist inside a set; only point at props that the set has.
Timing
- Anchor every action to the word where it should START (`at_word`), on the stressed word, not on filler words.
- Never leave more than ~4 seconds without a change on screen (an action, an overlay or a camera move). A hold of ~0.5-1 s after a big action is good.
- Nothing moves for its own sake: every action supports what is being said.
Teaching
- Introduce a term -> show it (pose or prop) -> name it (overlay) -> recap. Numbers become charts or a held sign. Processes become steps acted out in order.
  Comparisons use two characters or a compare overlay. Questions: the character thinks (`think`) and a `question` overlay may appear.
- Only show numbers, names and terms the speaker actually said. Never invent facts.
Continuity
- Reuse the same cast and sets. Do not rename characters. Change the set only when the story moves to a new place.
Social video
- The first second already shows the subject (a hook). Keep the lower part of the screen free for captions. End with a clear closing beat (recap or call to action).
Structure
- Cover EVERY beat exactly once, in order. A scene spans 1-3 beats (about 3-8 seconds), scene ids s1, s2, ...
- Prefer a few readable overlays per scene; do not discard requested content to meet an arbitrary count. Every `at_word` must be a word id inside that scene's beats. List actions and overlays in spoken order."""

OUTPUT = """\
OUTPUT
Return ONLY one JSON object (no commentary, no code fence) that matches the JSON schema below. Times are word ids, never seconds.
Free text is allowed only in `bubble`, overlay texts and labels, within their length limits. Everything else must be an exact value from the catalogue."""


def overlay_catalogue_text() -> str:
    lines = []
    for spec in component_catalogue():
        lines.append(f"- {spec['type']}: {spec['use_when']}  e.g. {json.dumps(spec['example'], ensure_ascii=False)}")
    return "\n".join(lines)


def transcript_text(tr: Transcript, beats: Beats) -> str:
    words = tr.by_id()
    out = []
    for b in beats.beats:
        ws = " ".join(f"{w}:{words[w].text}" for w in b.word_ids if w in words)
        out.append(f"[{b.id}] {b.start:.1f}-{b.end:.1f}s  {ws}")
    return "\n".join(out)


def examples_text() -> str:
    from .examples import EXAMPLES_SCRIPTS

    parts = []
    for i, (title, beats_txt, script) in enumerate(EXAMPLES_SCRIPTS, 1):
        parts.append(f"EXAMPLE {i}: {title}\nInput beats:\n{beats_txt}\nOutput:\n{json.dumps(script, ensure_ascii=False)}")
    return "\n\n".join(parts)


def build_prompt(tr: Transcript, beats: Beats, *, kind: str = "stick", language: str = "en", audience: str = "", tone: str = "", aspect: str = "9:16",
                 draft: Optional[dict] = None, hint: str = "", schema: Optional[dict] = None, with_examples: bool = True) -> tuple[str, str]:
    """(system, user) for complete_json."""
    system = ROLE.format(kind_text=KIND_TEXT.get(kind, "explainer")) + "\n\n" + CRAFT_RULES
    user = [f"VIDEO: kind={kind}; language={language}; audience={audience or 'general'}; tone={tone or 'clear and friendly'}; aspect={aspect}.",
            "TRANSCRIPT (beat id, time, then word id:word):", transcript_text(tr, beats), "", "CATALOGUE", C.catalogue_text(),
            "OVERLAYS (on-screen elements; each needs `type` and `at_word`, plus the fields shown):", overlay_catalogue_text()]
    if kind == "stick":
        user.append("\nFor kind=stick: define `cast` (1-3 characters) and `sets` first, give every scene a `set`, and give most scenes at least one action.")
    elif kind == "emoji":
        user.append("\nFor kind=emoji: leave `cast`, `sets` and `actions` empty. Every scene shows one to three big colour emoji (overlay type `sticker`, `emoji` = its hex code, "
                    "label = the word) and at most one `keyword` in type for the stressed word. No charts, cards or lists. Vary transition_in from scene to scene; "
                    "never use the same emoji in two scenes in a row.")
    else:
        user.append(f"\nFor kind={kind}: leave `cast` and `sets` empty and `actions` empty; design with overlays only.")
    if draft:
        user.append("\nDRAFT from the rule planner (improve it, keep what is good):\n" + json.dumps(draft, ensure_ascii=False)[:6000])
    if hint:
        user.append(f"\nUSER HINT: {hint}")
    if with_examples:
        user.append("\n" + examples_text())
    user.append("\n" + OUTPUT)
    if schema is not None:
        user.append("JSON SCHEMA:\n" + json.dumps(schema, ensure_ascii=False))
    return system, "\n".join(user)
