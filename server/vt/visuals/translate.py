"""Word -> English through Google Translate (deep-translator, no API key), so any language can reach the English visual dictionary.

Only single words/short phrases are sent (never audio or whole transcripts), results are cached on disk, and every failure
(offline, rate limit, library missing) silently falls back to the built-in dictionary. Disable with VT_TRANSLATE=0.
"""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata

from .. import paths
from ..util import read_json, write_json

_CACHE = paths.DATA / "translate_cache.json"
_lock = threading.Lock()
_mem: dict[str, str] | None = None


def enabled() -> bool:
    return os.environ.get("VT_TRANSLATE", "1") != "0"


def _load() -> dict[str, str]:
    global _mem
    if _mem is None:
        _mem = read_json(_CACHE, {}) or {}
    return _mem


def cached(word: str, src: str = "bn") -> str | None:
    """Offline lookup of an earlier translation ('' = tried, no answer)."""
    return _load().get(f"{src}:{unicodedata.normalize('NFC', word)}") or None


def prefetch(words: list[str], src: str = "bn") -> int:
    """Translate the words not cached yet (batched). Returns how many new translations were stored."""
    if not enabled():
        return 0
    cache = _load()
    todo = sorted({unicodedata.normalize("NFC", w) for w in words if w and f"{src}:{unicodedata.normalize('NFC', w)}" not in cache})
    if not todo:
        return 0
    try:
        from deep_translator import GoogleTranslator, MyMemoryTranslator
    except Exception:
        return 0
    engines = [GoogleTranslator(source=src, target="en"),
               MyMemoryTranslator(source={"bn": "bn-IN"}.get(src, src), target="en-US")]   # keyless fallback when Google throttles
    stored, fails = 0, 0
    for w in todo:                                          # one word at a time, paced under Google's ~5 requests/second
        t = None
        for eng in list(engines):
            try:
                t = (eng.translate(w) or "").strip().lower()
                break
            except Exception:
                if eng is engines[0]:
                    engines.append(engines.pop(0))          # throttled: try the other service first from now on
        if t is None:
            fails += 1
            if fails >= 3:
                break                                       # offline: stop, retried on the next run
            continue
        t = re.sub(r"^(the|a|an|to) ", "", t)
        cache[f"{src}:{w}"] = t if t and t != w.lower() and "MYMEMORY" not in t.upper() else ""
        stored += 1
        time.sleep(0.25)
    if stored:
        with _lock:
            write_json(_CACHE, cache)
    return stored
