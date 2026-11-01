"""Which words are KEY TERMS worth putting on screen?

An educational video should show "radiation", "gravity", "spaceship", not "fine", "leave", "close" or "interesting". English words are judged by
how often they are nouns (WordNet sense counts, prebuilt into design/icons/pos.json.gz by scripts/build_pos.py), how specific they are (word
frequency) and how central they are to this video (how often the speaker comes back to them). Bangla has no tagger here: Bangla words are
judged by specificity and repetition only.
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from functools import lru_cache
from typing import Iterable, Optional

from .. import paths

BN_RE = re.compile(r"[ঀ-৿]")
_PUNCT = " ,.।?!;:'\"“”‘’()[]-–—…"


def norm(w: str) -> str:
    return w.strip(_PUNCT).lower().replace("’", "'")


@lru_cache(maxsize=1)
def _pos() -> dict[str, list[float]]:
    p = paths.ICONS / "pos.json.gz"
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _variants(w: str) -> list[str]:
    out = [w]
    for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"), ("'s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            out.append(w[: -len(suf)] + rep)
    return out


ING_NOUNS = set("""building buildings painting paintings meeting meetings wedding clothing ceiling morning evening string spring pudding housing funding
training learning engineering marketing banking farming mining shipping earring painting drawing drawings recording recordings setting settings
feeling feelings beginning ending savings warning warnings opening offering offerings ceiling filling stuffing dumpling lightning""".split())


def shares(word: str) -> Optional[tuple[float, float, float]]:
    """(noun, verb, adjective) shares of an English word, or None if unknown."""
    w = norm(word)
    table = _pos()
    if w.endswith("ing") and len(w) > 5 and w not in ING_NOUNS:                     # "listening", "glowing": if the verb exists, the -ing form is the verb in speech
        for stem in (w[:-3], w[:-3] + "e", w[:-4]):
            if stem in table and table[stem][1] >= 0.5:
                n, vb, a = table.get(w, table[stem])
                return min(n, 0.3), max(vb, 0.6), a
    for v in _variants(w):
        if v in table:
            n, vb, a = table[v]
            if v != w and w.endswith("ing"):                  # "orbiting", "glowing": used as verb/adjective far more than as a noun
                n *= 0.35
            return n, vb, a
    return None


def noun_share(word: str) -> float:
    s = shares(word)
    return s[0] if s else (0.6 if BN_RE.search(word) else 0.5)


def zipf(word: str) -> float:
    try:
        from wordfreq import zipf_frequency

        w = norm(word)
        return zipf_frequency(w, "bn" if BN_RE.search(w) else "en")
    except Exception:
        return 4.0


def topic_counts(words: Iterable[str]) -> Counter:
    """How often each content word (by its simple stem) is said in the whole video."""
    c: Counter = Counter()
    for w in words:
        t = norm(w)
        if len(t) >= 3:
            c[_variants(t)[-1] if not BN_RE.search(t) else t] += 1
    return c


def _stem(w: str) -> str:
    t = norm(w)
    return _variants(t)[-1] if not BN_RE.search(t) else t


def score(word: str, topics: Optional[Counter] = None) -> float:
    """0..1: how much the word deserves to be shown as a key term."""
    t = norm(word)
    if len(t) < 3 or t.isdigit():
        return 0.0
    z = zipf(t)
    spec = 0.7 if z == 0 else max(0.0, min(1.0, (6.3 - z) / 3.3))      # "the" 7.7 -> 0, "radiation" 4.0 -> 0.7, "spaghettification" -> 0.7
    rep = min(1.0, ((topics or {}).get(_stem(t), 1) - 1) / 3)          # said 4+ times: central to the video
    if BN_RE.search(t):
        return 0.55 * spec + 0.45 * rep
    n = noun_share(t)
    return 0.45 * n + 0.3 * spec + 0.25 * rep


GENERIC = set("""thing things stuff bunch lot lots way ways kind kinds sort part parts piece bit bits place day days year years time times idea ideas fact facts
point points number numbers people person someone something everything anything nothing everyone guy guys man men woman women one ones side end start
line lines case cases example examples question questions answer reason reasons problem matter area areas level levels type types group""".split())


def topic_terms(words: Iterable[str], first: Iterable[str] = (), n: int = 3) -> list[str]:
    """What the video is about, best first, as spoken (not stems): content words scored by how often they are said, whether the first
    sentence says them (where a video states its subject: "Most people think *sleep* is lost time") and how specific they are."""
    surface: dict[str, Counter] = {}
    count: Counter = Counter()
    for w in words:
        t = norm(w)
        if not is_content_word(t):
            continue
        st = _stem(t)
        count[st] += 1
        surface.setdefault(st, Counter())[t] += 1
    opening = {_stem(norm(w)) for w in first}
    def weight(st: str) -> float:
        best = surface[st].most_common(1)[0][0]
        spec = 0.7 if zipf(best) == 0 else max(0.0, min(1.0, (6.3 - zipf(best)) / 3.3))
        return count[st] + (1.5 if st in opening else 0.0) + spec + (0.6 * noun_share(best) if not BN_RE.search(best) else 0.0)
    ranked = sorted(count, key=lambda st: -weight(st))
    return [surface[st].most_common(1)[0][0] for st in ranked[:n]]


def is_content_word(word: str) -> bool:
    """A word worth showing in big type when no picture fits: it carries meaning (a noun, verb or adjective that is not among the most common
    words), so it can never mean the wrong thing, unlike a picture. Looser than is_key_term, which decides what gets a picture."""
    t = norm(word)
    if BN_RE.search(t):
        return len(t) >= 2
    return len(t) >= 4 and t.isalpha() and zipf(t) < 5.6 and t not in GENERIC


def is_key_term(word: str, topics: Optional[Counter] = None) -> bool:
    t = norm(word)
    if t in GENERIC and (topics or {}).get(_stem(t), 1) < 4:
        return False
    if not BN_RE.search(t) and zipf(t) >= 6.0:                 # "the", "and", "your": said so often in every video that repetition must not promote them
        return False
    if BN_RE.search(t):
        return score(t, topics) >= 0.35
    s = shares(t)
    if s is not None and s[0] < 0.34 and ((topics or {}).get(_stem(t), 1) < 3):   # mostly a verb or adjective, and not the topic
        return False
    return score(t, topics) >= 0.42
