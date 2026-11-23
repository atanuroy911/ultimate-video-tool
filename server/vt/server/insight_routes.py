"""O7 (docs/plans/PLAN-OPENMOTION.MD): what only Video Tool knows about a video, for panels beside the HyperFrames Studio: the talk's outline (sections,
examples and whether each example got B-roll), the retention check of the newest export, and the notices (extras that were skipped)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter

from ..util import read_json
from .modules_routes import project_or_404

router = APIRouter(prefix="/api", tags=["insights"])


def outline_view(project) -> Optional[dict]:
    """The talk outline with each example's scenes and whether any of them shows B-roll (a picture, a clip, a shot, more than words)."""
    from .. import talk_outline as TO

    o = TO.load(project)
    if not o:
        return None
    sf, beats = project.scenes(), project.beats()
    bmap = {b.id: b for b in beats.beats}

    def span(sc):
        bs = [bmap[b] for b in sc.beats if b in bmap]
        return (float(bs[0].start), float(bs[-1].end)) if bs else None

    spans = [(sc, span(sc)) for sc in (sf.scenes if sf else [])]
    examples = []
    for e in o.get("examples", []):
        e0, e1 = float(e.get("start", 0)), float(e.get("end", 0))
        over = [sc for sc, s in spans if s and min(s[1], e1) > max(s[0], e0)]
        examples.append({"kind": e.get("kind", ""), "about": e.get("about", ""), "show": e.get("show", ""), "start": e0, "end": e1,
                         "scenes": [sc.id for sc in over], "broll": any(TO._is_broll(sc) for sc in over)})
    pick = lambda xs, *keys: [{k: x.get(k) for k in ("start", "end", *keys)} for x in xs or []]     # noqa: E731
    return {"sections": pick(o.get("sections"), "point"), "examples": examples, "keep": pick(o.get("keep_on_speaker"), "why"),
            "summary": o.get("summary", ""), "covered": sum(1 for e in examples if e["broll"])}


def retention_view(project) -> Optional[dict]:
    """The retention check of the newest export, if it was checked."""
    from .. import retention as RT

    files = sorted(project.exports_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True) if project.exports_dir.exists() else []
    if not files:
        return None
    card = RT.load(files[0].with_suffix(".retention.json"))
    if not card:
        return {"file": files[0].name, "checked": False}
    return {"file": files[0].name, "checked": True, "risk": card.get("risk"), "score": card.get("score"), "verdict": RT.verdict(card),
            "worst": card.get("worst", [])[:12], "hook_s": card.get("hook_s"), "longest_gap_s": card.get("longest_gap_s")}


@router.get("/projects/{pid}/insights")
def insights(pid: str) -> dict[str, Any]:
    p = project_or_404(pid)
    return {"outline": outline_view(p), "retention": retention_view(p), "notices": read_json(p.dir / "notices.json", []) or []}
