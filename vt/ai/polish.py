"""Transcript polish: a language model reads the transcript with context and SUGGESTS fixes for speech-recognition mistakes (names, terms,
Bangla/Banglish spellings). It never changes timings or the number of words: a suggestion replaces one word's text. The user accepts or rejects each one."""
from __future__ import annotations

from typing import Optional

from . import AIUnavailable, complete_json
from ..util import ProgressFn, noop_progress, now_iso, read_json, write_json

SCHEMA = {
    "type": "object",
    "properties": {"fixes": {"type": "array", "maxItems": 12, "items": {
        "type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string", "maxLength": 40}, "why": {"type": "string", "maxLength": 80}},
        "required": ["id", "text"]}}},
    "required": ["fixes"],
}

PROMPT = """A speech recogniser transcribed a recording ({lang}). Find words that are probably WRONG given the context (misheard names, terms, spellings)
and give the corrected spelling of that one word. Rules: only fix clear mistakes; one word in, one word out; keep the language and script; do not rephrase;
do not "improve" style; if nothing is wrong answer an empty list.

Each word is id:text.
{text}"""


def _chunks(beats, words, n: int = 8):
    for i in range(0, len(beats), n):
        grp = beats[i:i + n]
        yield " \n".join(" ".join(f"{w}:{words[w].text}" for w in b.word_ids if w in words) for b in grp), {w for b in grp for w in b.word_ids}


def suggest(project, progress: ProgressFn = noop_progress, provider=None) -> list[dict]:
    """Suggestions [{id, old, text, why, status:'pending'}], saved in polish.json (earlier decisions are kept)."""
    tr, beats = project.transcript(), project.beats()
    words = tr.by_id()
    prior = {s["id"]: s for s in (read_json(project.dir / "polish.json", {}) or {}).get("suggestions", [])}
    lang = "Bangla / Banglish" if project.meta().language == "bn" else "English"
    out = dict(prior)
    chunks = list(_chunks(beats.beats, words))
    for i, (text, ids) in enumerate(chunks):
        progress("polish", i / max(1, len(chunks)), f"Reading part {i + 1} of {len(chunks)}")
        try:
            r = complete_json(PROMPT.format(lang=lang, text=text), SCHEMA, provider=provider, max_tokens=600, timeout=240, temperature=0.0)
        except AIUnavailable as e:
            if not out and i == 0:
                raise
            break
        for f in r["fixes"]:
            wid, new = f["id"].strip(), f["text"].strip()
            w = words.get(wid)
            if not w or wid not in ids or not new or new == w.text or len(new.split()) != 1:
                continue                                             # unknown id, no change, or it is not one word for one word
            if wid in prior and prior[wid]["status"] != "pending":
                continue
            out[wid] = {"id": wid, "old": w.text, "text": new, "why": f.get("why", ""), "status": "pending"}
    res = sorted(out.values(), key=lambda s: words[s["id"]].start if s["id"] in words else 0)
    write_json(project.dir / "polish.json", {"at": now_iso(), "suggestions": res})
    progress("polish", 1.0, f"{sum(1 for s in res if s['status'] == 'pending')} suggestions")
    return res


def load(project) -> list[dict]:
    return (read_json(project.dir / "polish.json", {}) or {}).get("suggestions", [])


def decide(project, accept: list[str], reject: list[str]) -> dict:
    """Mark suggestions accepted/rejected. Accepted ones become word edits (the existing edits.json mechanism); returns what to apply."""
    sug = load(project)
    edits = read_json(project.dir / "edits.json", {"words": {}}) or {"words": {}}
    applied = []
    for s in sug:
        if s["id"] in accept and s["status"] == "pending":
            s["status"] = "accepted"
            edits["words"].setdefault(s["id"], {})["text"] = s["text"]
            applied.append(s["id"])
        elif s["id"] in reject and s["status"] == "pending":
            s["status"] = "rejected"
    write_json(project.dir / "polish.json", {"at": now_iso(), "suggestions": sug})
    if applied:
        write_json(project.dir / "edits.json", edits)
    return {"applied": applied}
