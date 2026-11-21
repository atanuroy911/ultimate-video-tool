"""Automatic quality scores for a Video Script (used to compare the AI's script with the rule script on a transcript set)."""
from __future__ import annotations

import re

from ..schema import Beats, Transcript
from .models import VideoScript
from .validate import validate_script

METRICS = ["valid", "coverage", "no_idle_gap", "number_fidelity", "variety", "fit"]


def score(script: VideoScript | dict, tr: Transcript, beats: Beats) -> dict[str, float]:
    """Each metric is 0..1 (higher is better)."""
    data = script.model_dump(by_alias=True) if isinstance(script, VideoScript) else script
    s = VideoScript.model_validate(data)
    words = tr.by_id()
    errs = validate_script(data, tr, beats)
    total = max(0.1, beats.beats[-1].end - beats.beats[0].start) if beats.beats else 0.1
    # time points where something happens
    pts = []
    for sc in s.scenes:
        pts += [words[a.at_word].start for a in sc.actions if a.at_word in words]
        pts += [words[o["at_word"]].start for o in sc.overlays if o.get("at_word") in words]
    starts = [b.start for sc in s.scenes for b in beats.beats if b.id == sc.beats[0]]      # a new scene is a change too
    pts = sorted(pts + starts)
    t0, t1 = (beats.beats[0].start, beats.beats[-1].end) if beats.beats else (0, 1)
    gaps = [b - a for a, b in zip([t0] + pts, pts + [t1])]
    max_gap = max(gaps) if gaps else total
    per_min = len([1 for sc in s.scenes for _ in sc.actions]) / (total / 60)
    covered = {b for sc in s.scenes for b in sc.beats}
    text = " ".join(b.text for b in beats.beats)
    nums = set(re.findall(r"\d[\d,.]*", text))
    shown = " ".join(str(v) for sc in s.scenes for o in sc.overlays for v in _strings(o)) + " " + " ".join(a.bubble or "" for sc in s.scenes for a in sc.actions)
    fid = 1.0 if not nums else sum(1 for n in nums if n.strip(",.") in shown) / len(nums)
    over = [len(sc.overlays) for sc in s.scenes]
    verbs = [a.do for sc in s.scenes for a in sc.actions]
    types = [o.get("type") for sc in s.scenes for o in sc.overlays]
    n = max(1, len(s.scenes))
    # variety: how many different things happen (verbs and overlay kinds), relative to what a video of this length could show
    variety = min(1.0, (len(set(verbs)) / max(1, min(len(verbs), 6)) + len(set(types)) / max(1, min(len(types), 4))) / 2) if (verbs or types) else 0.0
    return {
        "valid": 1.0 if not errs else max(0.0, 1 - len(errs) / 10),
        "coverage": len(covered) / max(1, len(beats.beats)),
        "no_idle_gap": 1.0 if max_gap <= 4 else max(0.0, 1 - (max_gap - 4) / 6),
        "number_fidelity": fid,
        "variety": variety,
        "fit": fit_score(s, beats),
    }


ROLE_RULES = [                                   # sentence feature -> what a good plan shows for it
    (re.compile(r"\?|[?]"), {"think", "question"}),
    (re.compile(r"\d"), {"hold_sign", "count", "big_number", "ring", "stat_row", "value_card", "bar_chart", "line_chart", "gauge", "pictogram", "price_tag", "icon_row"}),
    (re.compile(r"\b(means?|is called|stands for)\b|মানে", re.I), {"point", "write_board", "definition"}),
    (re.compile(r"\b(first|then|next|finally|step)\b", re.I), {"steps", "flow", "timeline", "count", "walk_to"}),
]


def fit_score(s: VideoScript, beats: Beats) -> float:
    """Share of sentences with a recognisable feature (question, number, definition, sequence) that the plan answers with a fitting verb or graphic."""
    by_beat = {}
    for sc in s.scenes:
        shown = {a.do for a in sc.actions} | {o.get("type") for o in sc.overlays}
        for b in sc.beats:
            by_beat[b] = shown
    hits = total = 0
    for b in beats.beats:
        for pat, good in ROLE_RULES:
            if pat.search(b.text):
                total += 1
                hits += bool(good & by_beat.get(b.id, set()))
    return hits / total if total else 1.0


def _strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, (str, int, float)):
        yield o


def compare(ai_scores: dict[str, float], rule_scores: dict[str, float]) -> dict:
    """Metrics where the AI is at least as good, and whether it wins (4 of 6, per docs/history/plan-2026-10.md H.2-1)."""
    ge = [m for m in METRICS if ai_scores[m] >= rule_scores[m] - 1e-9]
    gt = [m for m in METRICS if ai_scores[m] > rule_scores[m] + 1e-9]
    return {"at_least_as_good": ge, "better": gt, "wins": len(ge) >= 4 and len(gt) >= 1}
