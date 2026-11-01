"""Turn bits of speech into text that is fit to print on screen, or reject them.

Speech (and especially subtitles) arrives in fragments: "However, before you do", "a tiny", "and here". An infographic built from such pieces
looks broken, so every phrase that goes into a card, list, step, definition or quote passes through `tidy()`:
  * leading discourse words are removed ("however", "and", "so", "well", "okay", "first"),
  * trailing words that leave the phrase hanging are removed ("... where gravity and", "... if"),
  * it is cut on a word boundary to fit, never mid-word,
  * it must still contain a real content word; otherwise it is rejected (None) and the builder picks another scene type.
"""
from __future__ import annotations

import re
from typing import Optional

LEAD = set("""however but and so well okay ok also then now first second third next finally lastly anyway basically actually like um uh
because since though although while yet plus or before after just really oh right alright and,""".split()) | {"কিন্তু", "আর", "এবং", "তাহলে", "তো", "তবে", "যদিও", "আসলে", "প্রথমে", "এরপর", "তারপর"}
TRAIL = set("""a an the of to and or but if so as at by for from in into on with that which who whose where when than then is are was were be been
being has have had do does did can could will would should may might must not no it its this these those their there our your my his her
i you we they he she me us them very really just also about like""".split()) | {"ও", "আর", "এবং", "যে", "কিন্তু", "তো"}
LEAD_PHRASE = re.compile(r"^(in short|in summary|to sum up|in other words|for example|for instance|as a result|on the other hand|at the end of the day|you know|i mean|let's say|so basically)[,\s]+", re.I)
PRONOUNS = set("i you we they he she it this that these those there here me us them him her".split())
_P = " ,.;:!?।'\"“”‘’()[]—–-…"


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", (text or "").strip()) if w.strip(_P)]


def _n(w: str) -> str:
    return w.strip(_P).lower()


def tidy(text: str, max_chars: int = 36, min_content: int = 1, keep_case: bool = True, whole: bool = False) -> Optional[str]:
    """whole=True: a complete sentence (question, quote) keeps its ending; it is only rejected if it does not fit."""
    from ..visuals import terms as T

    text = LEAD_PHRASE.sub("", (text or "").strip())
    ws = _words(text)
    while ws and _n(ws[0]) in LEAD:
        ws = ws[1:]
    # fit on word boundaries
    out: list[str] = []
    for w in ws:
        if len(" ".join(out + [w]).strip(_P)) > max_chars:
            if whole:
                return None
            break
        out.append(w)
    while out and _n(out[-1]) in TRAIL and not whole:
        out = out[:-1]
    if not out:
        return None
    content = [w for w in out if _n(w) not in TRAIL and _n(w) not in PRONOUNS and _n(w) not in LEAD and len(_n(w)) >= 3]
    if len(content) < min_content:
        return None
    if len(out) == 1 and not whole and not (T.is_key_term(out[0]) or T.BN_RE.search(out[0])):
        return None                                           # a single word must be a key term ("radiation"), not "fine"
    s = " ".join(out).strip(_P.replace("%", "").replace("?", "")).strip()
    s = s.rstrip(",;:—–-")
    if s and not keep_case:
        s = s[0].upper() + s[1:]
    return s or None


def tidy_all(items: list[str], max_chars: int = 36, need: int = 2) -> Optional[list[str]]:
    """All items tidy, distinct and at least `need` of them, else None (a list with one broken item is not shown at all)."""
    out = []
    for it in items:
        t = tidy(it, max_chars)
        if t is None:
            return None
        if t.lower() in (x.lower() for x in out):
            return None
        out.append(t)
    return out if len(out) >= need else None


def is_sentence(text: str) -> bool:
    """A complete sentence (capital or Bangla start, ending punctuation), not a fragment cut out of one."""
    t = (text or "").strip()
    return bool(t) and (t[0].isupper() or bool(re.match(r"[ঀ-৿]", t))) and t[-1] in ".!?।\"”"
