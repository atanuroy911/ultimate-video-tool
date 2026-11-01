"""Tighten: cut a long talk down to the length the platform rewards, the way an editor would.

An editor does not only remove pauses; when a vertical video runs to 2 minutes they drop the sentences the story can live
without. This picks those sentences from the context reading (vt/context.py: each sentence's role and importance 0-3, and
what it continues, explains or answers):

* never the first sentence (the hook), never importance 3 (the point of the video), never a call to action;
* never a sentence that a kept sentence explains, answers, contrasts with or continues (it would lose its meaning);
* filler first (importance 0), then recaps, asides and extra examples; among equals the sentence least central to the talk
  (LexRank, Erkan & Radev 2004: how many other sentences resemble it) goes first; without a context reading centrality alone
  stands in for importance;
* at most MAX_SHARE of the sentences, so a video is shortened, never gutted.

The target: `options.target_length` "keep" (never), "60" / "90" (seconds), or "auto" (the default): a vertical video over
AUTO_OVER seconds is brought to AUTO_TARGET; wide and square videos are kept whole. Every dropped sentence is written with
its reason to `tighten.json`, so it is shown and can be put back.
"""
from __future__ import annotations

import re
from typing import Optional

from . import saliency

AUTO_OVER, AUTO_TARGET = 90.0, 60.0
MAX_SHARE = 0.4
SOFT_ROLES = {"recap": 0, "personal": 1, "example": 2, "opinion": 3, "story": 4, "proof": 5}       # what goes first, after filler
PROTECTED_ROLES = {"hook", "cta"}
REASONS = {"recap": "repeats what was already said", "personal": "a personal aside", "example": "an extra example", "opinion": "an aside, not the point",
           "story": "a side detail", "proof": "extra support for a point already made"}


OPENERS = re.compile(r"\b(once upon a time|long ago|there (once )?(lived|was)|one day)\b|একদিন|একবার|এক সময়|অনেক দিন আগে", re.I)
DIALOGUE = re.compile(r"\b(said|asked|replied|told|shouted|whispered)\b|বলল|বললেন|জিজ্ঞেস|উত্তর দিল", re.I)


def is_narrative(mood: str | None, sentences: dict[str, dict], texts: list[str] = ()) -> bool:
    """A story: by the context's mood, when many sentences are story events, or by the words (a story opener in the first
    sentences, people talking in many of them). The AI reading sometimes files a parable under "motivation"."""
    roles = [s.get("role") for s in sentences.values()]
    if mood == "story" or (roles and roles.count("story") >= 0.4 * len(roles)):
        return True
    texts = list(texts)
    return bool(texts) and (any(OPENERS.search(t) for t in texts[:3]) or sum(bool(DIALOGUE.search(t)) for t in texts) >= 0.15 * len(texts))


def target_seconds(setting: str, aspect: str, duration: float) -> Optional[float]:
    if setting == "keep":
        return None
    if setting in ("60", "90"):
        return float(setting) if duration > float(setting) else None
    return AUTO_TARGET if aspect == "9:16" and duration > AUTO_OVER else None


def centrality_importance(centrality: float) -> int:
    """Importance 0-2 from LexRank centrality (mean 1.0), used when no AI reading of the sentence exists."""
    return 0 if centrality < 0.6 else 1 if centrality < 1.1 else 2


def choose(beats: list[dict], sentences: dict[str, dict], target: float, narrative: bool = False) -> list[dict]:
    """beats: [{id, start, end, text}] in output time; sentences: beat id -> {role, importance, relation, rel_to}.
    `narrative`: a story, where every event carries the plot: only filler (importance 0) may go, never an event.
    Returns [{beat, text, reason}] to drop, in time order."""
    if not beats:
        return []
    total = beats[-1]["end"] - beats[0]["start"]
    needed = {s.get("rel_to") for s in sentences.values() if s.get("relation") in ("explains", "answers", "contrasts", "continues", "example") and s.get("rel_to")}
    centrality = saliency.lexrank([b.get("text", "") for b in beats])
    cands = []
    for i, b in enumerate(beats):
        s = sentences.get(b["id"], {})
        imp, role = int(s.get("importance", centrality_importance(centrality[i]))), s.get("role", "claim")
        if i == 0 or imp >= 3 or role in PROTECTED_ROLES or b["id"] in needed:
            continue
        if imp >= 2 or (narrative and (imp > 0 or role == "story")):
            continue
        rank = (imp, SOFT_ROLES.get(role, 9), round(centrality[i], 2), -(b["end"] - b["start"]))
        cands.append((rank, b, role, imp))
    cands.sort(key=lambda c: c[0])
    out, limit = [], int(len(beats) * MAX_SHARE)
    for _, b, role, imp in cands:
        if total <= target or len(out) >= limit:
            break
        out.append({"beat": b["id"], "text": b["text"], "reason": "filler, says nothing new" if imp == 0 else REASONS.get(role, "less important than the rest")})
        total -= b["end"] - b["start"]
    order = {b["id"]: i for i, b in enumerate(beats)}
    return sorted(out, key=lambda d: order[d["beat"]])
