"""Look ahead on a long talk (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C10): read the whole transcript before planning, and find
the stretches where the speaker gives an example (a story, a case, numbers, a comparison, a list, a demonstration, an analogy)
and the stretches that must stay on the speaker. The director then designs B-roll for the examples.

A long talk does not fit a small model at once, so it is read in overlapping chunks of sentences. Each chunk is given the summary
of everything before it, so an example that refers back ("like the beetle case earlier") is still understood. The result is
`talk_outline.json` in the project: sentences (with times), sections, examples and keep-on-speaker stretches, all by sentence number.
The AI decides what is an example; code only splits, merges and checks the numbers it gives back.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field

from .util import now_iso, write_json

CHUNK = 60            # sentences per AI call (about 900 words of speech)
OVERLAP = 8           # sentences shared with the previous chunk, so an example cut by the chunk edge is seen whole
KINDS = ("story", "case", "numbers", "comparison", "list", "demonstration", "analogy", "definition")
OUTLINE_FILE = "talk_outline.json"


class Section(BaseModel):
    first: int = Field(description="Number of the section's first sentence.")
    last: int = Field(description="Number of its last sentence.")
    point: str = Field(max_length=200, description="What this part of the talk is about, in one short line.")


class Example(BaseModel):
    first: int = Field(description="Number of the first sentence of the example.")
    last: int = Field(description="Number of its last sentence.")
    kind: Literal["story", "case", "numbers", "comparison", "list", "demonstration", "analogy", "definition"]
    about: str = Field(max_length=200, description="What the example is, in plain words.")
    show: str = Field(max_length=300, description="What a viewer should see while it is said: concrete things, numbers, steps. Only what the words say.")


class Keep(BaseModel):
    first: int
    last: int
    why: str = Field(max_length=120, description="Why the speaker should stay on screen: opening, closing, opinion, emotion, talking to the viewer.")


class ChunkAnswer(BaseModel):
    summary: str = Field(max_length=1200, description="The whole talk so far in a few sentences, including this part: its topic, its sections and its examples by name.")
    sections: list[Section] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    keep_on_speaker: list[Keep] = Field(default_factory=list)


SYSTEM = (
    "You read a long talk before it is edited into a video. The editor will show B-roll (pictures, diagrams, numbers, short clips) over the parts where "
    "the speaker gives an EXAMPLE, and keep the speaker on screen elsewhere. Your job is only to read and mark; you do not design anything.\n"
    "An example is a stretch where the speaker makes an idea concrete: a story or anecdote, a real case or study, numbers and results, a comparison, "
    "a list of steps or items, a demonstration being described, an analogy, or a definition of a term the audience may not know.\n"
    "Mark an example from its first to its last sentence (use the sentence numbers you are given). It is usually 2 to 12 sentences. Do not mark "
    "greetings, the plan of the talk, opinions or the closing as examples: those are keep_on_speaker.\n"
    "For each example, `show` says what a viewer could see while it is said, using only what the words say (no invented facts or numbers).\n"
    "Sections: split the part you are given into its topics. Summary: rewrite the summary of the whole talk so far to include this part."
)


def sentences(words: list[dict]) -> list[dict]:
    """Group timed words into sentences: {n, text, start, end}. Ends on . ? ! or a long pause; never longer than 40 words."""
    out: list[dict] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (float(nxt["start"]) - float(w["end"])) if nxt else 9.0
        if re.search(r"[.?!]['\")]*$", str(w.get("text", "")).strip()) or gap > 1.2 or len(cur) >= 40:
            out.append({"n": len(out) + 1, "text": " ".join(str(x.get("text", "")).strip() for x in cur).strip(),
                        "start": round(float(cur[0]["start"]), 2), "end": round(float(cur[-1]["end"]), 2)})
            cur = []
    return out


def _prompt(chunk: list[dict], summary: str, total: int) -> str:
    lines = "\n".join(f"{s['n']}. [{s['start']:.0f}s] {s['text']}" for s in chunk)
    before = f"Summary of the talk so far:\n{summary}\n\n" if summary else "This is the start of the talk.\n\n"
    return (f"{before}The talk has {total} sentences. Here are sentences {chunk[0]['n']} to {chunk[-1]['n']}:\n\n{lines}\n\n"
            "Mark the sections, examples and keep-on-speaker stretches in these sentences only, and update the summary.")


def _clip(a: int, b: int, lo: int, hi: int) -> Optional[tuple[int, int]]:
    a, b = max(lo, min(a, b)), min(hi, max(a, b))
    return (a, b) if a <= b else None


def merge_examples(found: list[dict]) -> list[dict]:
    """Examples seen twice (in the overlap of two chunks) become one: overlapping ranges merge, the longer description wins."""
    out: list[dict] = []
    for e in sorted(found, key=lambda e: (e["first"], -e["last"])):
        if out and e["first"] <= out[-1]["last"]:
            last = out[-1]
            if (e["last"] - e["first"]) > (last["last"] - last["first"]):
                last.update({k: e[k] for k in ("kind", "about", "show")})
            last["last"] = max(last["last"], e["last"])
        else:
            out.append(dict(e))
    return out


def outline(words: list[dict], *, provider=None, progress: Callable[[float, str], None] = lambda f, m: None,
            ask: Optional[Callable[[str, str], dict]] = None) -> dict:
    """The whole talk's outline. `ask(system, prompt) -> dict` may be given for tests; otherwise the chosen AI answers."""
    from . import ai

    sents = sentences(words)
    if not sents:
        return {"sentences": [], "sections": [], "examples": [], "keep_on_speaker": [], "summary": ""}
    if ask is None:
        def ask(system: str, prompt: str) -> dict:
            return ai.complete_json(prompt, ChunkAnswer.model_json_schema(), system=system, model_cls=ChunkAnswer, provider=provider,
                                    max_tokens=3000, timeout=600, retries=1)
    summary = ""
    sections: list[dict] = []
    examples: list[dict] = []
    keep: list[dict] = []
    step = CHUNK - OVERLAP
    starts = list(range(0, len(sents), step)) or [0]
    for k, at in enumerate(starts):
        chunk = sents[at:at + CHUNK]
        if not chunk or (k and len(chunk) <= OVERLAP):
            break
        progress(k / len(starts), f"Reading the talk: sentences {chunk[0]['n']} to {chunk[-1]['n']} of {len(sents)}")
        ans = ChunkAnswer.model_validate(ask(SYSTEM, _prompt(chunk, summary, len(sents))))
        lo, hi = chunk[0]["n"], chunk[-1]["n"]
        summary = ans.summary.strip() or summary
        for s in ans.sections:
            if (r := _clip(s.first, s.last, lo, hi)) and not (sections and r[0] <= sections[-1]["last"]):
                sections.append({"first": r[0], "last": r[1], "point": s.point})
        for e in ans.examples:
            if r := _clip(e.first, e.last, lo, hi):
                examples.append({"first": r[0], "last": r[1], "kind": e.kind, "about": e.about, "show": e.show})
        for s in ans.keep_on_speaker:
            if r := _clip(s.first, s.last, lo, hi):
                keep.append({"first": r[0], "last": r[1], "why": s.why})
    by_n = {s["n"]: s for s in sents}
    examples = merge_examples(examples)
    for e in examples + sections + keep:
        e["start"], e["end"] = by_n[e["first"]]["start"], by_n[e["last"]]["end"]
    progress(1.0, f"Read the talk: {len(sections)} sections, {len(examples)} examples")
    return {"sentences": sents, "sections": sections, "examples": examples, "keep_on_speaker": keep, "summary": summary}


def build(project, *, provider=None, progress: Callable[[float, str], None] = lambda f, m: None) -> dict:
    """Read the project's transcript (the edited words) and save talk_outline.json."""
    tr = project.transcript()
    words = [w.model_dump() if hasattr(w, "model_dump") else dict(w) for w in (tr.words if tr else [])]
    words = [w for w in words if not w.get("cut")]
    out = outline(words, provider=provider, progress=progress)
    out["made_at"] = now_iso()
    write_json(project.dir / OUTLINE_FILE, out)
    return out
