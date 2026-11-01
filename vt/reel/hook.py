"""Hook proposals (docs/plans/PLAN-REEL-DIRECTOR.MD R8): when the first line of a script is weak, offer up to two better openings. Nothing is applied silently.

The rules only ever trim or move the author's own sentences, so they cannot invent a fact. An AI rewrite of the first line is offered too, but only when every number and
every longer word in it is already in the script (`grounded`).
"""
from __future__ import annotations

import re
from typing import Optional

from .reading import rules_hook

GREETING = re.compile(r"^\W*(hi|hello|hey|welcome|good (morning|evening|afternoon)|what'?s up|today|in this video|before we (start|begin)|thanks for|don'?t forget to)", re.I)
FILLER = re.compile(r"\b(welcome back|my channel|i want to talk about|i('| a)m going to (talk|tell)|let'?s (get started|dive in))\b", re.I)
WEAK_BELOW = 0.4


def sentences(script: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", script.strip()) if s.strip()]


def _signal(s: str) -> float:
    """How much a sentence sounds like an opening: a question, a prohibition, a number, a claim."""
    h = rules_hook(s)
    score = h.strength
    if re.search(r"\d", s):
        score += 0.15
    if len(s.split()) > 22:
        score -= 0.2
    if GREETING.match(s) or FILLER.search(s):
        score -= 0.5
    return score


def grounded(text: str, script: str) -> bool:
    """Every number and every word of more than three letters in `text` is somewhere in `script`."""
    have = set(re.findall(r"[\w$%]+", script.casefold()))
    return all(t in have for t in re.findall(r"[\w$%]+", text.casefold()) if t.isdigit() or len(t) > 3)


def is_weak(script: str) -> bool:
    s = sentences(script)
    return bool(s) and (_signal(s[0]) < WEAK_BELOW)


def propose(script: str, *, ai_rewrites: Optional[list[str]] = None) -> list[dict]:
    """Up to two openings, each {"id", "why", "script"} where `script` is the whole script with that change. `ai_rewrites` are candidate first lines from a model."""
    s = sentences(script)
    if len(s) < 2 or not is_weak(script):
        return []
    out: list[dict] = []
    drop = 0
    while drop < len(s) - 1 and (GREETING.match(s[drop]) or FILLER.search(s[drop])) and len(s[drop].split()) < 30:
        drop += 1
    if drop:
        out.append({"id": "cut-greeting", "why": f"Starts with the point: the first {drop} sentence{'s' if drop > 1 else ''} said hello, not something new.", "script": " ".join(s[drop:]), "kind": "trim"})
    rest = s[drop:] if drop else s
    best = max(range(len(rest)), key=lambda i: _signal(rest[i]))
    if best > 0 and _signal(rest[best]) >= WEAK_BELOW:
        out.append({"id": "lead-with-strongest", "why": "Opens with the line most likely to make someone stay, then tells the rest in the original order.",
                    "script": " ".join([rest[best]] + rest[:best] + rest[best + 1:]), "kind": "reorder"})
    for i, text in enumerate(ai_rewrites or []):
        if len(out) >= 2:
            break
        text = text.strip()
        if text and grounded(text, script):
            out.append({"id": f"rewrite-{i + 1}", "why": "A sharper first line that says only what the script already says.", "script": " ".join([text] + (s[drop:] if drop else s[1:])), "kind": "rewrite"})
    return out[:2]


def ai_first_lines(script: str) -> list[str]:
    """Ask the language AI for two stronger first lines. Anything it cannot do returns []: the rules' proposals stand on their own."""
    try:
        from ..ai import complete_json
        from ..ai.providers import ai_enabled

        if not ai_enabled():
            return []
        schema = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}, "maxItems": 2}}, "required": ["lines"]}
        data = complete_json("Rewrite the FIRST sentence of this script as a stronger hook (a question, a surprising claim or a warning). Use only facts, numbers and names that the "
                             "script already contains. One sentence each, at most 18 words.\n\n" + script[:2500], schema, system="You write hooks for short videos. Never add facts.",
                             retries=1, max_tokens=300, temperature=0.4, check=lambda d: [] if all(grounded(x, script) for x in d.get("lines", [])) else ["a line contains a fact that is not in the script"])
        return [x for x in data.get("lines", []) if isinstance(x, str)]
    except Exception:                                                                     # noqa: BLE001
        return []
