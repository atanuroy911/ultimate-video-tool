"""Talk to the director: "make it funnier", "the owner should be an old man", "less talking, more action".

The person's request goes to the AI with the same prompt the director was written with (role, craft rules, transcript with word
ids, catalogue, schema), the current script in full, and the request. The answer is repaired, validated, checked by the critic
and filled by the enricher like any other script, then applied (the previous plan is kept for undo). The reply says in plain
words what changed. The director never changes the words, the voice or the timing of speech: only what is seen.
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from .. import ai
from ..planner.catalogue import all_icon_names
from ..project import Project
from ..schema import ScenesFile
from ..util import now_iso, read_json, write_json
from .compile import to_json_schema
from .models import VideoScript
from .prompt import build_prompt
from . import repairs as REPAIRS
from .repairs import repairer
from .validate import validate_script

HISTORY = 12


def history_path(p: Project):
    return p.dir / "director_chat.json"


def history(p: Project) -> list[dict]:
    return (read_json(history_path(p), {}) or {}).get("messages", [])


def director_state(p: Project, plan: Optional[ScenesFile] = None) -> dict:
    """Everything one Director turn replaces, kept together so undo cannot leave the script newer than the visible plan."""
    from .service import SCRIPT_PLAN

    plan = plan or p.scenes()
    return {
        "plan": plan.model_dump(exclude_none=True) if plan else None,
        "script": read_json(p.dir / "video_script.json", None),
        "script_plan": read_json(p.dir / SCRIPT_PLAN, None),
        "report": read_json(p.dir / "director.json", None),
        "status": p.meta().status,
    }


def restore_director_state(p: Project, raw: dict) -> None:
    """Validate a state completely, then restore it. Composition and change notification belong to the calling route."""
    from .service import SCRIPT_PLAN

    if not isinstance(raw, dict) or not raw.get("plan"):
        raise ValueError("The Director history entry has no plan.")
    plan = ScenesFile.model_validate(raw["plan"])
    script = VideoScript.model_validate(raw["script"]) if raw.get("script") else None
    script_plan = ScenesFile.model_validate(raw["script_plan"]) if raw.get("script_plan") else None
    report = raw.get("report")
    if report is not None and not isinstance(report, dict):
        raise ValueError("The Director history entry has an invalid report.")
    status = raw.get("status")
    if status is not None and not isinstance(status, str):
        raise ValueError("The Director history entry has an invalid project status.")

    p.save_scenes(plan)
    files = {
        p.dir / "video_script.json": script.model_dump(by_alias=True, exclude_none=True) if script else None,
        p.dir / SCRIPT_PLAN: script_plan.model_dump(exclude_none=True) if script_plan else None,
        p.dir / "director.json": report,
    }
    for path, value in files.items():
        if value is None:
            path.unlink(missing_ok=True)
        else:
            write_json(path, value)
    if status is not None:
        p.update_meta(status=status)


EDITS_SHOWN = 8            # scenes edited on the timeline that are spelled out for the director; the rest are only named
EDITS_CHARS = 6000


def _timeline_edits(p: Project) -> str:
    """What was changed on the timeline since the script was written, for the director's prompt: it must know what is really on screen, and that those
    scenes stay as they are unless its new script changes them."""
    from .service import edits_since_script

    try:
        edits = edits_since_script(p)
    except Exception:                                              # noqa: BLE001  a missing record never stops a request
        edits = []
    if not edits:
        return ""
    shown, size = [], 0
    for e in edits[:EDITS_SHOWN]:
        text = json.dumps(e, ensure_ascii=False)
        if size + len(text) > EDITS_CHARS:
            text = json.dumps({"scene": e["scene"], "change": e["change"]}, ensure_ascii=False)
        size += len(text)
        shown.append(text)
    more = [e["scene"] for e in edits[EDITS_SHOWN:]]
    return ("\n\nEDITED ON THE TIMELINE since this script was written (by the person, or by your own last look at the frames). These scenes are on screen as "
            "shown here, not as the script says. They stay exactly like this unless your new script changes that scene; when you do change such a scene, "
            "carry over what was fixed in it:\n" + "\n".join(shown) + (f"\nAlso edited: {', '.join(more)}." if more else ""))


def _current(p: Project, kind: str) -> VideoScript:
    from .rules_stick import rules_script
    from .service import current_script

    data = current_script(p)
    if data:
        return VideoScript.model_validate(data)
    return rules_script(p.transcript(), p.beats(), p.scenes(), kind=kind, language=p.meta().language, aspect=p.meta().aspect)


def changed_scenes(old: VideoScript, new: VideoScript) -> list[str]:
    """Scene ids whose visible direction changed in this turn, in the new script's order."""
    o = {s.id: s for s in old.scenes}
    return [s.id for s in new.scenes if s.id not in o or s.model_dump(exclude={"id"}) != o[s.id].model_dump(exclude={"id"})]


def changed_plan_scenes(old: Optional[ScenesFile], new: Optional[ScenesFile]) -> tuple[list[str], list[str]]:
    """Visible compiled-scene changes, plus removed ids that cannot be linked to a clip."""
    if not new:
        return [], [s.id for s in old.scenes] if old else []
    old_scenes = old.scenes if old else []
    before = {s.id: s for s in old_scenes}
    positions = {s.id: i for i, s in enumerate(old_scenes)}
    global_change = bool(old and (old.theme != new.theme or old.story_cast != new.story_cast))
    touched = [
        s.id for i, s in enumerate(new.scenes)
        if global_change or s.id not in before or positions[s.id] != i
        or before[s.id].model_dump(exclude_none=True) != s.model_dump(exclude_none=True)
    ]
    now = {s.id for s in new.scenes}
    removed = [s.id for s in old_scenes if s.id not in now]
    return touched, removed


def changes(old: VideoScript, new: VideoScript, touched: Optional[list[str]] = None, removed: Optional[list[str]] = None) -> str:
    """What changed, in one or two plain sentences."""
    touched = changed_scenes(old, new) if touched is None else touched
    removed = removed or []
    o = {s.id: s for s in old.scenes}
    out = []
    if touched:
        out.append(f"Changed {len(touched)} of {len(new.scenes)} scenes.")
        n = {s.id: s for s in new.scenes}
        for sid in touched[:3]:                                    # what now happens there, in words
            if sid not in n:
                continue
            before = {(a.who, a.do) for a in o[sid].actions} if sid in o else set()
            names = {c.id: c.name or c.id for c in new.cast}
            fresh = [f"{a.do.replace('_', ' ')} ({names.get(a.who, a.who)})" for a in n[sid].actions if (a.who, a.do) not in before]
            if fresh:
                out.append(f"Scene {sid[1:] if sid[1:].isdigit() else sid} now has: " + ", ".join(fresh[:5]) + ".")
    if removed:
        labels = [f"Scene {sid[1:] if sid[1:].isdigit() else sid}" for sid in removed]
        out.append("Removed " + ", ".join(labels) + ".")
    oc, nc = {c.id: c for c in old.cast}, {c.id: c for c in new.cast}
    added = [c.name or c.id for i, c in nc.items() if i not in oc]
    gone = [c.name or c.id for i, c in oc.items() if i not in nc]
    restyled = [c.name or c.id for i, c in nc.items() if i in oc and c.model_dump() != oc[i].model_dump()]
    if added:
        out.append("New in the cast: " + ", ".join(added) + ".")
    if gone:
        out.append("Left the cast: " + ", ".join(gone) + ".")
    if restyled:
        out.append("New look for " + ", ".join(restyled) + ".")
    if {s.id for s in new.sets} != {s.id for s in old.sets}:
        out.append("The places changed.")
    return " ".join(out) or "Nothing needed to change."


def talk(p: Project, message: str, provider: Optional[ai.Provider] = None, say: Optional[Callable[[float, str], None]] = None, author: str = "person") -> dict:
    """Apply the request. Returns {ok, reply, scenes_changed}; raises ai.AIUnavailable when no AI can answer."""
    from .critic import enrich
    from .planner import revise
    from .service import apply_script, save_report, script_kind

    say = say or (lambda f, m: None)
    message = message.strip()[:600]
    meta = p.meta()
    kind = script_kind(p)
    tr, beats = p.transcript(), p.beats()
    with p.scenes_lock():
        previous_plan = p.scenes()
        previous_state = director_state(p, previous_plan)
        cur = _current(p, kind)
    schema = to_json_schema()
    pk = "stick" if cur.kind == "cartoon" else cur.kind          # a cartoon is directed as a stick-figure story, then drawn with illustrated characters
    system, user = build_prompt(tr, beats, kind=pk, language=meta.language, aspect=meta.aspect, schema=schema)
    past = "\n".join(f"- {m['text']}" for m in history(p)[-6:] if m["from"] == "person")
    user += ("\n\nCURRENT SCRIPT (it is on screen now; change only what the request needs, keep the rest exactly):\n"
             + json.dumps(cur.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)
             + _timeline_edits(p)
             + (f"\n\nEARLIER REQUESTS (already done, keep them):\n{past}" if past else "")
             + f"\n\nREQUEST FROM THE PERSON: {message}\n"
             "Return the whole script as JSON. Never change the words, beats or word ids; you direct what is seen.")
    icons = all_icon_names()
    media = {m.id for m in meta.planner_media()}
    say(0.1, "The director is reading your note")
    notes: list[dict] = []
    data = ai.complete_json(user, schema, system=system, provider=provider, max_tokens=8000, timeout=600, cache=False, retries=1,
                            repair=repairer(tr, beats, pk, notes),
                            check=lambda d: validate_script(d, tr, beats, icons, media))
    new = VideoScript.model_validate(data)
    new.kind = pk
    say(0.6, "Checking the new cut")
    new = revise(new, tr, beats, system, schema, pk, icons, media, provider, lambda f, m: say(0.6 + 0.2 * f, m))
    new, _ = enrich(new, tr, beats)
    from .animals import animalize

    new, _ = animalize(new)
    if cur.kind == "cartoon":
        from ..art.toon import toonify

        new = toonify(new)
    who = (provider or ai.current_provider()).name
    res = apply_script(p, new.model_dump(by_alias=True, exclude_none=True), planner="claude" if who in ("anthropic", "claude_cli") else "llm",
                       expected_plan=previous_plan.model_dump(exclude_none=True) if previous_plan else None,
                       previous=cur.model_dump(by_alias=True, exclude_none=True))       # a revision: only the scenes it changes are replaced, the timeline's other edits stay
    touched: list[str] = []
    removed: list[str] = []
    if not res.get("ok"):
        reply = ("I left the video unchanged because it was edited while I was working. Send this request again and I will use the newer version."
                 if res.get("conflict") else "I could not make that work: " + "; ".join(res.get("errors", [])[:3]))
        ok = False
    else:
        try:
            REPAIRS.record(p, notes, "the AI")                                              # Details, Problems: what the script became
        except Exception:                                                                   # noqa: BLE001
            pass
        applied = ScenesFile.model_validate(res["plan"])
        touched, removed = changed_plan_scenes(previous_plan, applied)
        reply = changes(cur, new, touched, removed)
        lost = res.get("replaced_edits") or []
        if lost:                                                   # said plainly: the person can undo, or ask for it back
            names = ", ".join(f"Scene {sid[1:] if sid[1:].isdigit() else sid}" for sid in lost[:6])
            reply += f" {names} had your own edits on the timeline; my new version replaced them there (Undo brings them back)."
        save_report(p, new, tr, beats, f"chat: {message[:60]}")
        ok = True
    if author == "person":
        from .. import taste

        taste.learn_note(message)
    msgs = history(p) + [{"from": author, "text": message, "at": now_iso()}, {"from": "director", "text": reply, "at": now_iso(), "ok": ok}]
    write_json(history_path(p), {"messages": msgs[-2 * HISTORY:]})
    return {
        "ok": ok,
        "reply": reply,
        # The job result gives the editor an exact undo step. This snapshot is captured before the director starts applying its script,
        # so later plan saves cannot overwrite the one-file scenes.prev.json backup before Ctrl+Z reaches this change.
        "previous_plan": previous_plan.model_dump(exclude_none=True) if ok and previous_plan else None,
        "previous_state": previous_state if ok and previous_plan else None,
        "changed_scenes": touched if ok else [],
        "replaced_edits": (res.get("replaced_edits") or []) if ok else [],
        "removed_scenes": removed if ok else [],
    }
