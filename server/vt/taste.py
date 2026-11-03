"""The creator's taste, learned from what they change, so the next video needs fewer changes.

A human editor who works with someone for a while stops making the same mistakes. Three things are remembered here
(`taste.json` in the data folder; nothing leaves the computer):

* **spellings**: when the same word is corrected to the same spelling in two different videos, the correction joins the global
  glossary (paths.GLOBAL_GLOSSARY) and every later video gets it right by itself. One-off fixes stay one-off.
* **choices** (look, caption style): when the person picks the same thing for two videos in a row, it becomes the default.
* **notes to the director**: the last requests ("make it funnier", "less talking") go to the director of the next video as
  the creator's usual wishes.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from . import paths
from .util import now_iso, read_json, write_json

SPELL_PROJECTS = 2
CHOICE_RUN = 2
NOTES_KEPT = 20


def _path():
    return paths.DATA / "taste.json"


def _load() -> dict:
    d = read_json(_path(), {}) or {}
    d.setdefault("fixes", {})
    d.setdefault("choices", {})
    d.setdefault("notes", [])
    return d


def learn_fix(heard: str, fixed: str, project_id: str) -> bool:
    """A word the speech model got wrong was corrected. Returns True when it was learned for every future video."""
    heard, fixed = heard.strip(), fixed.strip()
    if not heard or not fixed or heard == fixed or len(heard) < 2:
        return False
    d = _load()
    key = f"{heard}\t{fixed}"
    seen = set(d["fixes"].get(key, [])) | {project_id}
    d["fixes"][key] = sorted(seen)
    write_json(_path(), d)
    if len(seen) < SPELL_PROJECTS:
        return False
    g = read_json(paths.GLOBAL_GLOSSARY, {}) or {}
    if g.get(heard) == fixed:
        return False
    g[heard] = fixed
    write_json(paths.GLOBAL_GLOSSARY, g)
    return True


def learn_choice(kind: str, value: str) -> Optional[str]:
    """The person chose `value` for `kind` (e.g. theme). Returns the value when it has become their preference."""
    d = _load()
    hist = (d["choices"].get(kind, []) + [value])[-10:]
    d["choices"][kind] = hist
    write_json(_path(), d)
    return value if len(hist) >= CHOICE_RUN and len(set(hist[-CHOICE_RUN:])) == 1 else None


def learn_note(text: str) -> None:
    d = _load()
    d["notes"] = (d["notes"] + [{"text": text.strip()[:200], "at": now_iso()}])[-NOTES_KEPT:]
    write_json(_path(), d)


def director_hint() -> str:
    """The creator's usual wishes, for the director of a new video ("" when there are none)."""
    notes = [n["text"] for n in _load()["notes"]]
    if not notes:
        return ""
    common = [t for t, _ in Counter(x.lower() for x in notes).most_common(3)]
    recent = [t for t in reversed(notes) if t.lower() not in common][:2]
    return "This creator's earlier notes to the director (follow them where they fit this video): " + "; ".join(common + recent)
