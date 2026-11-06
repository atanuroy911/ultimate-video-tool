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


def _current(p: Project, kind: str) -> VideoScript:
    from .rules_stick import rules_script
    from .service import current_script

    data = current_script(p)
    if data:
        return VideoScript.model_validate(data)
    return rules_script(p.transcript(), p.beats(), p.scenes(), kind=kind, language=p.meta().language, aspect=p.meta().aspect)


def changes(old: VideoScript, new: VideoScript) -> str:
    """What changed, in one or two plain sentences."""
    o = {s.id: s for s in old.scenes}
    touched = [s.id for s in new.scenes if s.id not in o or s.model_dump(exclude={"id"}) != o[s.id].model_dump(exclude={"id"})]
    out = []
    if touched:
        out.append(f"Changed {len(touched)} of {len(new.scenes)} scenes.")
        n = {s.id: s for s in new.scenes}
        for sid in touched[:3]:                                    # what now happens there, in words
            before = {(a.who, a.do) for a in o[sid].actions} if sid in o else set()
            names = {c.id: c.name or c.id for c in new.cast}
            fresh = [f"{a.do.replace('_', ' ')} ({names.get(a.who, a.who)})" for a in n[sid].actions if (a.who, a.do) not in before]
            if fresh:
                out.append(f"Scene {sid[1:] if sid[1:].isdigit() else sid} now has: " + ", ".join(fresh[:5]) + ".")
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
    cur = _current(p, kind)
    schema = to_json_schema()
    pk = "stick" if cur.kind == "cartoon" else cur.kind          # a cartoon is directed as a stick-figure story, then drawn with illustrated characters
    system, user = build_prompt(tr, beats, kind=pk, language=meta.language, aspect=meta.aspect, schema=schema)
    past = "\n".join(f"- {m['text']}" for m in history(p)[-6:] if m["from"] == "person")
    user += ("\n\nCURRENT SCRIPT (it is on screen now; change only what the request needs, keep the rest exactly):\n"
             + json.dumps(cur.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)
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
    res = apply_script(p, new.model_dump(by_alias=True, exclude_none=True), planner="claude" if who in ("anthropic", "claude_cli") else "llm")
    if not res.get("ok"):
        reply = "I could not make that work: " + "; ".join(res.get("errors", [])[:3])
        ok = False
    else:
        try:
            REPAIRS.record(p, notes, "the AI")                                              # Details, Problems: what the script became
        except Exception:                                                                   # noqa: BLE001
            pass
        reply = changes(cur, new)
        save_report(p, new, tr, beats, f"chat: {message[:60]}")
        ok = True
    if author == "person":
        from .. import taste

        taste.learn_note(message)
    msgs = history(p) + [{"from": author, "text": message, "at": now_iso()}, {"from": "director", "text": reply, "at": now_iso(), "ok": ok}]
    write_json(history_path(p), {"messages": msgs[-2 * HISTORY:]})
    return {"ok": ok, "reply": reply}
