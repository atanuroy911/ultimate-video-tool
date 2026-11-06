"""Direction for the AI director: the lessons finished videos taught us, written once and read by every AI that directs a video.

These are not checks. The AI directs the video; it reads these lessons the way a director reads notes from the last cut (Claude or Codex over
MCP, the local AI, the Cartoon 2 scene designer all get `prompt(scope)`). Code never rejects a plan for them.

Adding a lesson: append a Rule with the incident in `why` (date, video) and the direction in `say`. Scopes: "plan" (every scene plan),
"story" (Cartoon 2 scenes), "cartoon" (Cartoon 1 scenes). Keep `say` short and concrete: it is a prompt.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    scopes: tuple[str, ...]
    say: str        # what the AI is told, one or two sentences
    why: str        # the incident that taught it


RULES: list[Rule] = [
    Rule("kind-people", ("plan", "story", "cartoon"),
         "Draw people kindly and with dignity, so any viewer is comfortable: never mock a body, skin colour, religion, job or accent; no stereotypes. "
         "Families, elders and children look warm and respectful; prefer calm or smiling faces unless the words are sad or frightening.",
         "Owner, 2026-11-05: 'Characters should be acceptable to other viewers'."),
    Rule("no-violence", ("plan", "story", "cartoon"),
         "Show only what the words say. No violence, blood or weapons on screen; a frightening moment is a dark background and a face.",
         "Story-engine house rule, kept for every cartoon."),
    Rule("show-it-once", ("plan", "cartoon", "story"),
         "Show each thing once in a scene: a number already on a card is not counted again beside it, a clock at ten needs no '10' next to it.",
         "2026-11-05 Cartoon 1 test: '250' appeared twice and '10' sat beside a clock at ten."),
    Rule("faces-stay-clear", ("plan", "cartoon", "story"),
         "Nothing covers a face. When characters fill the frame, give cards and stickers x and y where nobody stands (the sky, a wall, an empty side).",
         "2026-11-05 Cartoon 1 test: a big '$' sticker sat on the hero's face in five scenes."),
    Rule("cast-by-id", ("story",),
         "Refer to a character by its cast id (hero, mother ...) in `char`, never by its name.",
         "2026-11-05 Cartoon 2 test 3: the AI wrote 'Maya' as the char and the video fell back to the rule planner."),
    Rule("pronouns-decide-gender", ("story", "cartoon"),
         "A character's look follows the script: she/her is a woman or girl, he/him a man or boy; a named person keeps one look for the whole video.",
         "2026-11-05 Cartoon 2 test 3: Maya was drawn as a boy."),
    Rule("one-language", ("plan", "story", "cartoon"),
         "Everything on screen is in the narration's language and script: role names (Mom, not মা), labels and digits.",
         "2026-11-05 Cartoon 2 test 3: an English video called the mother 'মা'."),
    Rule("short-tags", ("story",),
         "A scene tag is one or two whole words (a place or a time), or none.",
         "2026-11-05 Cartoon 2: tags were cut mid-word ('Mother Hugs Daug')."),
    Rule("choices-win", ("plan", "story", "cartoon"),
         "What the user chose (voice, music, sounds, captions, style) is kept exactly; only what they left on Automatic is yours to decide.",
         "Owner, 2026-11-04: 'if i choose settings rather auto detect it should respect it'."),
]


def rules_for(scope: str) -> list[Rule]:
    return [r for r in RULES if scope in r.scopes]


def prompt(scope: str = "plan", start: int = 1) -> str:
    """The notes for one kind of director, numbered, ready to append to its brief."""
    lines = [f"{n}. {r.say}" for n, r in enumerate(rules_for(scope), start)]
    return "DIRECTOR'S NOTES (lessons from earlier videos; use your judgement)\n" + "\n".join(lines)


def listing() -> list[dict]:
    """Every note for the Studio, the CLI and MCP (one list behind all three)."""
    return [{"id": r.id, "scopes": list(r.scopes), "say": r.say, "why": r.why} for r in RULES]
