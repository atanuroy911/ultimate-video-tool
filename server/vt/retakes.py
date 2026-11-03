"""Retakes and false starts: what an editor cuts first from a phone recording.

People recording themselves stop and start again: "Today I want to- today I want to talk about money", or say a whole
sentence twice because the first one came out wrong. The editor keeps the last take. This works on the recognised words
(source time, before any cut), so it needs no model and runs offline:

* the words are split into phrases at pauses (> PAUSE s) and after sentence punctuation;
* a phrase is a **false start** when a later phrase within WINDOW s begins with the same words (at least 2, and most of it);
* a phrase is a **retake** when a later phrase within WINDOW s says nearly the same thing (similarity >= SIMILAR, 4+ words);
* inside one phrase, a run of 3+ words said twice in a row ("in the year in the year 2020") keeps the second copy.

It is deliberately conservative: a short rhetorical repeat ("never, never") is kept, and nothing is cut from a typed script.
Every cut carries the text and a plain reason, so the editor can show it and the person can undo it.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

PAUSE = 0.45
WINDOW = 15.0
SIMILAR = 0.8
_END = re.compile(r"[.?!।]$")
_STRIP = re.compile(r"[^\wঀ-৿]+")


def _norm(t: str) -> str:
    return _STRIP.sub("", t.lower())


def phrases(words: list[dict]) -> list[list[int]]:
    out: list[list[int]] = []
    for i, w in enumerate(words):
        if not out or w["start"] - words[i - 1]["end"] > PAUSE or _END.search(words[i - 1]["text"].strip()):
            out.append([])
        out[-1].append(i)
    return out


def _prefix(a: list[str], b: list[str]) -> int:
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    return k


def find_retakes(words: list[dict]) -> list[dict]:
    """[{start, end, text, reason, words: [indices]}] for the takes to cut, in time order."""
    toks = [_norm(w["text"]) for w in words]
    ph = [[i for i in p if toks[i]] for p in phrases(words)]
    ph = [p for p in ph if p]
    cut: list[dict] = []
    done: set[int] = set()
    for x, a in enumerate(ph):
        ta = [toks[i] for i in a]
        for b in ph[x + 1:x + 4]:
            if words[b[0]]["start"] - words[a[-1]]["end"] > WINDOW:
                break
            tb = [toks[i] for i in b]
            k = _prefix(ta, tb)
            # a restart repeats the whole abandoned phrase (or all but a cut-off last word: "tal-" then "talk"); "some said 500, some said 800" is a list
            cut_off = k == len(ta) - 1 and k < len(tb) and (tb[k].startswith(ta[-1]) or words[a[-1]]["text"].rstrip().endswith(("-", "—", "…", "...")))
            reworded = k >= 4 and k >= 0.6 * len(ta)                 # "put away ten percent of your pay" -> "... of what you earn": a long shared start is a second try
            if len(ta) >= 2 and k >= 2 and (k == len(ta) or cut_off or reworded) and len(ta) <= len(tb) and k < len(tb):
                reason = "false start, said again right after"
            elif len(ta) >= 4 and SequenceMatcher(None, ta, tb).ratio() >= SIMILAR:
                reason = "said twice, the last take is kept"
            else:
                continue
            cut.append({"words": a, "reason": reason})
            done.update(a)
            break
    for p in ph:                                            # "in the year in the year 2020": a stumble without a pause
        if p[0] in done:
            continue
        tp = [toks[i] for i in p]
        n = len(tp)
        for size in range(min(6, n // 2), 2, -1):
            hit = next((s for s in range(n - 2 * size + 1) if tp[s:s + size] == tp[s + size:s + 2 * size]), None)
            if hit is not None:
                cut.append({"words": p[hit:hit + size], "reason": "stumble, the words were repeated"})
                break
    out = []
    for c in sorted(cut, key=lambda c: c["words"][0]):
        ws = [words[i] for i in c["words"]]
        out.append({"start": ws[0]["start"], "end": ws[-1]["end"], "text": " ".join(w["text"] for w in ws), "reason": c["reason"], "words": c["words"]})
    return out
