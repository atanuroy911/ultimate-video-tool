"""What the page's layout guard found in a video, told in plain words (plan decision 1: the director's word is final).

A plan made by the built-in rules keeps the guard: the page shrinks an element that runs off the frame, hides one that runs off the frame anyway, is too small to read or
sits on another one, and Details, Problems says so, scene by scene. A plan an AI directed is never changed by code: the same findings are measured (renderer/scripts/frame-facts.mjs),
told to the director, and what is still there after its rounds is listed in the Quality check (director_review.py). The person's own edits are not touched either way.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from .compose import FORMATS
from .compose.composer import AI_PLANNERS
from .modules.calls import append_call
from .project import Project
from .util import file_hash, now_iso, read_json, write_json

REPORT = "layout_guard.json"
FIX = "The rules planned this scene. Give it fewer or smaller things in the editor, or let an AI direct the video: it is told about this and fixes it itself."


def enabled() -> bool:
    """On unless VT_LAYOUT_CHECK=0 (the tests turn it off: it opens the composition in a browser)."""
    return os.environ.get("VT_LAYOUT_CHECK", "1") != "0"


def says(g: dict) -> str:
    """One thing the guard did, as a clause: 'the tag had letters too small to read on a phone, so it was hidden'."""
    kind = str(g.get("type", "")).replace("_", " ")
    if kind.startswith("prop:"):
        return f"the prop {kind[5:]} was cut by the shot, so it was not drawn"
    if g.get("rule") == "cut-off":
        return f"the {kind} ran off the frame, so it was " + ("made smaller to fit" if g.get("fix") == "shrunk" else "hidden")
    if g.get("rule") == "too-small":
        return f"the {kind} had letters too small to read on a phone, so it was hidden"
    if g.get("rule") == "overlap":
        return f"the {kind} sat on top of another element, so it was hidden"
    return f"the {kind} was changed"


def by_scene(sf, found: list[dict]) -> list[dict]:
    """The guard's decisions grouped by scene, in the plan's order: [{scene, number, says: [clause, ...]}]."""
    order = {s.id: i + 1 for i, s in enumerate(sf.scenes)}
    rows: dict[str, list[str]] = {}
    for g in found:
        if g.get("directed") or g.get("fix") not in ("shrunk", "dropped"):                  # what an AI directed was only measured
            continue
        said = rows.setdefault(g.get("scene", ""), [])
        if says(g) not in said:                                                              # the pages of one scene tell the same thing: once
            said.append(says(g))
    return [{"scene": sid, "number": order.get(sid), "says": parts} for sid, parts in sorted(rows.items(), key=lambda kv: order.get(kv[0], 999))]


def record(p: Project) -> list[dict]:
    """After a plan made without an AI is composed: open the composition the way the renderer does, read what the guard did and write it to Details, Problems.
    Nothing happens when this exact plan was recorded before, or when the page cannot be opened (this is a report, never a reason to stop a video)."""
    if not enabled():
        return []
    sf = p.scenes()
    if sf is None or sf.planner in AI_PLANNERS:
        return []
    done = read_json(p.dir / REPORT, None) or {}
    now = file_hash(p.scenes_path)
    if done.get("scenes_hash") == now:
        return done.get("scenes", [])
    from .render.hyperframes import guard_log

    try:
        found = guard_log(p.comp_dir / FORMATS[p.meta().aspect]["tag"])
    except Exception as e:                                                      # noqa: BLE001  no browser, no report
        write_json(p.dir / REPORT, {"at": now_iso(), "scenes_hash": now, "scenes": [], "error": f"{type(e).__name__}: {str(e)[:200]}"})
        return []
    rows = by_scene(sf, found)
    for row in rows:
        append_call(p.dir, {
            "id": "c" + uuid.uuid4().hex[:12], "module": "layout.guard", "caller": {"kind": "rules", "who": "rules"},
            "why": "The built-in rules keep a layout guard: what runs off the frame, is too small to read or sits on another element is fixed or hidden.",
            "inputs": {"scene": row["scene"]}, "status": "changed", "level": "warn",
            "plain": f"Scene {row['number'] or row['scene']}: " + "; ".join(row["says"]) + ".", "fix": FIX,
        })
    write_json(p.dir / REPORT, {"at": now_iso(), "scenes_hash": now, "scenes": rows})
    return rows
