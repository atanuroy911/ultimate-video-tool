"""Correcting the transcript a sentence at a time (or all of it): the owner pastes the right text, the words keep their real times.

The new text is lined up against the words now in the transcript (difflib, ignoring case and punctuation). Words that match keep their time and take the new
spelling; a replaced run is spread over the old words (a longer replacement is joined onto the last one, a shorter one drops the extra words); inserted
words ride on the word before them; missing words are dropped. Nothing here touches the audio: dropped words only disappear from captions and plans.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_PUNCT = re.compile(r"[^\wঀ-৿]+", re.UNICODE)


def norm(t: str) -> str:
    return _PUNCT.sub("", unicodedata.normalize("NFC", t).casefold())


def tokens(text: str) -> list[str]:
    return [t for t in unicodedata.normalize("NFC", text).split() if t]


def align(old: list[tuple[str, str]], new_text: str) -> dict[str, dict]:
    """old: [(word id, current text)]. Returns {word id: {"text": ...} or {"drop": True}} for every word that changes."""
    new = tokens(new_text)
    a = [norm(t) for _, t in old]
    b = [norm(t) for t in new]
    out: dict[str, dict] = {}
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    last_kept: str | None = None                       # the word an insertion rides on
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                wid, cur = old[i1 + k]
                if new[j1 + k] != cur:
                    out[wid] = {"text": new[j1 + k]}
                last_kept = wid
        elif op == "delete":
            for wid, _ in old[i1:i2]:
                out[wid] = {"drop": True}
        elif op == "insert":
            if last_kept is not None:
                base = out.get(last_kept, {}).get("text") or dict(old)[last_kept]
                out[last_kept] = {"text": " ".join([base, *new[j1:j2]])}
            elif old:                                  # at the very start: ride on the first old word
                wid, cur = old[0]
                out[wid] = {"text": " ".join([*new[j1:j2], out.get(wid, {}).get("text") or cur])}
        else:                                          # replace
            ids = [wid for wid, _ in old[i1:i2]]
            toks = new[j1:j2]
            for k, wid in enumerate(ids):
                if k < len(ids) - 1 and k < len(toks):
                    out[wid] = {"text": toks[k]}
                elif k == len(ids) - 1 and k < len(toks):
                    out[wid] = {"text": " ".join(toks[k:])}            # the last old word carries whatever is left
                else:
                    out[wid] = {"drop": True}
            last_kept = ids[min(len(ids), len(toks)) - 1] if toks else last_kept
    return out


def merge(edits: dict, changes: dict[str, dict]) -> dict:
    """Fold align()'s changes into edits.json (word id -> {"text", "cut", "drop"})."""
    words = dict(edits.get("words", {}))
    for wid, ch in changes.items():
        cur = dict(words.get(wid, {}))
        cur.pop("drop", None)
        cur.update(ch)
        words[wid] = cur
    return {**edits, "words": words}
