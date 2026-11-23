"""What repair_script changed in a director's Video Script, told instead of done silently (plan decision 1, step B4).

`repair_script` fixes what is safely fixable and describes each change as a note {scene, says, meaning}: `meaning` True when the repair changed what the director wrote (a word moved,
a text cut short, a value left out, scenes restructured), False when it only filled in the obvious (a synonym, a default side). A director that can answer (Claude or Codex over MCP,
`apply_script(strict=True)`) gets the first kind back as errors and the second as `repairs`. For a director that cannot (the local AI, or one answering a single question) both go to
Details, Problems, scene by scene, so the person can see what the script became.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Optional

from ..modules.calls import append_call
from ..project import Project
from ..schema import Beats, Transcript
from .validate import repair_script

FIX = "The script is used as it became. If the change is not what you want, edit the scene, or ask the director again and it will rewrite the scene."


def repairer(tr: Transcript, beats: Beats, kind: Optional[str], notes: list[dict], frame: Optional[tuple[int, int]] = None) -> Callable[[Any], Any]:
    """The `repair=` of ai.complete_json: repairs the reply and keeps the notes of the answer that is finally used (the last one repaired) in `notes`."""
    def repair(data: Any) -> Any:
        mine: list[dict] = []
        out = repair_script(data, tr, beats, kind, notes=mine, frame=frame) if isinstance(data, dict) else data
        notes[:] = mine
        return out
    return repair


def meaning(notes: list[dict]) -> list[str]:
    return [n["says"] for n in notes if n.get("meaning")]


def small(notes: list[dict]) -> list[str]:
    return [n["says"] for n in notes if not n.get("meaning")]


def record(p: Project, notes: list[dict], who: str = "the director", what: str = "Video Script") -> list[dict]:
    """Details, Problems: one warning per scene for what the repair changed in what `who` wrote, and one note for the small things it filled in. Nothing is written for a script that needed nothing."""
    out = []
    by_scene: dict[Optional[int], list[str]] = {}
    for n in notes:
        if n.get("meaning"):
            by_scene.setdefault(n.get("scene"), []).append(n["says"].split(": ", 1)[1] if n.get("scene") else n["says"])
    for scene, parts in sorted(by_scene.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        out.append({"id": "c" + uuid.uuid4().hex[:12], "module": "script.repair", "caller": {"kind": "rules", "who": "rules"},
                    "why": f"The {what} {who} wrote had values the app cannot use as written, so the app repaired them.",
                    "inputs": {"scene": scene} if scene else {}, "status": "changed", "level": "warn",
                    "plain": (f"Scene {scene}: " if scene else "") + "; ".join(parts) + ".", "fix": FIX})
    tidy = small(notes)
    if tidy:
        out.append({"id": "c" + uuid.uuid4().hex[:12], "module": "script.repair", "caller": {"kind": "rules", "who": "rules"},
                    "why": "; ".join(tidy)[:1500], "inputs": {}, "status": "changed", "level": "info",
                    "plain": f"The {what} was tidied: {len(tidy)} small thing(s) were filled in or moved a little."})
    return [append_call(p.dir, e) for e in out]
