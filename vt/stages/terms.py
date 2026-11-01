"""English terms inside Bangla speech ("Banglish").

The Bangla speech model writes English words in Bangla script (ফ্ল্যাট, নেট ইয়েল্ড). Each project chooses how they appear:

  * "mixed"  (default): English terms in Latin letters  ->  flat, net yield
  * "bangla":           English terms in Bangla script  ->  ফ্ল্যাট, নেট ইয়েল্ড

design/terms.json maps an English term to the Bangla-script spellings the model produces. Users add their own pairs in the
project glossary (explicit pairs always win). Only whole words are mapped; common Bangla case suffixes stay attached
(ফ্ল্যাটের -> flatের).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Optional

from .. import paths
from ..util import read_json
from .words import PUNCT_STRIP

SUFFIXES = ["দের", "গুলো", "গুলি", "টাকে", "ের", "কে", "টা", "টি", "তে", "য়", "র", "ে", "ও"]
_BN = re.compile(r"[ঀ-৿]")


def _nfc(s: str) -> str:
    """Bengali has two encodings of the same letter (e.g. য় as U+09DF or as য + nukta). Compare only in NFC."""
    return unicodedata.normalize("NFC", s)


@lru_cache(maxsize=1)
def _terms() -> dict[str, list[str]]:
    data = read_json(paths.DESIGN / "terms.json", {}) or {}
    return {k: [_nfc(x) for x in (v if isinstance(v, list) else [v])] for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def _bn_to_en() -> dict[str, str]:
    out: dict[str, str] = {}
    for en, spellings in _terms().items():
        for s in spellings:
            out[s] = en
    return out


def _split_suffix(core: str, known: dict[str, str]) -> Optional[tuple[str, str]]:
    if core in known:
        return core, ""
    for suf in SUFFIXES:
        if core.endswith(suf) and core[: -len(suf)] in known:
            return core[: -len(suf)], suf
    return None


# A dependent vowel sign cannot stand after a Latin letter (it renders as a dotted circle), so a Latin base followed by a Bangla
# suffix that starts with one is written with the independent letter: market + ে -> market-এ
_INDEPENDENT = {"া": "আ", "ি": "ই", "ী": "ঈ", "ু": "উ", "ূ": "ঊ", "ে": "এ", "ৈ": "ঐ", "ো": "ও", "ৌ": "ঔ"}


def join_latin_suffix(base: str, suffix: str) -> str:
    if suffix and suffix[0] in _INDEPENDENT:
        return base + "-" + _INDEPENDENT[suffix[0]] + suffix[1:]
    return base + suffix


def to_policy(text: str, policy: str) -> str:
    """Apply the script policy to one word (punctuation preserved)."""
    text = _nfc(text)
    core = text.strip(PUNCT_STRIP)
    if not core:
        return text
    i = text.find(core)
    pre, post = text[:i], text[i + len(core):]
    if policy == "mixed":
        hit = _split_suffix(core, _bn_to_en())
        if hit:
            base, suf = hit
            return pre + join_latin_suffix(_bn_to_en()[base], suf) + post
    elif policy == "bangla":
        low = core.lower()
        terms = _terms()
        if low in terms:
            return pre + terms[low][0] + post
        # a Latin term with a Bangla suffix (flatের) goes back to Bangla script
        m = re.fullmatch(r"([A-Za-z]+)-?([ঀ-৿]+)", core)
        if m and m.group(1).lower() in terms:
            suf = m.group(2)
            back = {v: k for k, v in _INDEPENDENT.items()}
            if "-" in core and suf[0] in back:                 # the independent letter written after a hyphen becomes the sign again
                suf = back[suf[0]] + suf[1:]
            return pre + terms[m.group(1).lower()][0] + suf + post
    return text
