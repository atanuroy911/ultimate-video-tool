"""Raw ASR words (source time) -> transcript.json (output time, ids, language tags, glossary, fillers) and beats."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from ..schema import Beat, Beats, Cuts, Transcript, Word

BN_RE = re.compile(r"[ঀ-৿]")
LATIN_RE = re.compile(r"[A-Za-z]")
SENTENCE_END = tuple("।.?!")
PUNCT_STRIP = " \t\n.,;:!?।\"'()[]{}“”‘’—–-…"

# Standalone fillers (compared after punctuation stripping, lower-cased)
FILLERS = {
    "bn": {"উম", "উমম", "আঁ", "আ", "এ", "অ", "হুম", "হুমম", "এ্যা", "আহ", "উহ", "ইয়ে"},
    "en": {"um", "umm", "uh", "uhh", "er", "erm", "hmm", "ah", "eh"},
}
FILLER_SET = FILLERS["bn"] | FILLERS["en"]


def norm_token(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip(PUNCT_STRIP).lower()


def fix_latin_vowel_sign(text: str) -> str:
    """'marketে' -> 'market-এ' (a vowel sign after a Latin letter renders as a dotted circle)."""
    from .terms import join_latin_suffix

    return re.sub(r"([A-Za-z0-9]+)([া-ৌ][ঀ-৿]*)", lambda m: join_latin_suffix(m.group(1), m.group(2)), text)


def detect_lang(text: str) -> str:
    if BN_RE.search(text):
        return "bn"
    if LATIN_RE.search(text):
        return "en"
    return "other"


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    """Replace a word using the glossary (case-insensitive, punctuation preserved)."""
    text = unicodedata.normalize("NFC", text)
    core = text.strip(PUNCT_STRIP)
    if not core:
        return text
    norm = {unicodedata.normalize("NFC", k): v for k, v in glossary.items()}   # same letter, two encodings: compare in NFC
    repl = norm.get(core) or norm.get(core.lower())
    if not repl:
        return text
    i = text.find(core)
    return text[:i] + repl + text[i + len(core):]


def find_fillers(raw: list[dict]) -> set[int]:
    """Indexes of filler words and of immediately repeated words ('মানে মানে')."""
    out: set[int] = set()
    for i, w in enumerate(raw):
        n = norm_token(w["text"])
        if n in FILLER_SET:
            out.add(i)
            continue
        if i + 1 < len(raw) and n and n == norm_token(raw[i + 1]["text"]) and raw[i + 1]["start"] - w["end"] < 0.35 and len(n) > 1:
            out.add(i)
    return out


def build_transcript(raw: dict, cuts: Cuts, glossary: Optional[dict[str, str]] = None, language: str = "bn",
                     edits: Optional[dict[str, dict]] = None, policy: str = "mixed") -> Transcript:
    """Map word times through the cut list, drop words that fall inside removed regions, tag, and number them.

    Word ids come from the raw ASR index (w1, w2...), so they stay stable when cuts change.
    `edits` is {word_id: {"text": str, "cut": bool}} made by the user in the Studio; it is applied last.
    `policy` ("mixed" | "bangla") decides how English terms inside Bangla speech are written (see stages/terms.py);
    explicit glossary pairs and user edits always win over it.
    """
    from .terms import to_policy

    glossary = glossary or {}
    edits = edits or {}
    words: list[Word] = []
    prev_end = 0.0
    for idx, w in enumerate(raw["words"], 1):
        s_src, e_src = float(w["start"]), float(w["end"])
        if e_src < s_src:
            e_src = s_src + 0.05
        # how much of the word survives the cuts?
        kept_len = sum(max(0.0, min(e, e_src) - max(s, s_src)) for s, e in cuts.keep)
        if kept_len < 0.4 * max(e_src - s_src, 0.04):
            continue
        s = cuts.map_time_nearest(s_src)
        e = cuts.map_time_nearest(e_src)
        s = max(s, prev_end)
        if e <= s:
            e = s + 0.06
        wid = f"w{idx}"
        ed = edits.get(wid, {})
        if ed.get("drop"):                                  # removed by a transcript correction (the audio is untouched)
            continue
        heard = unicodedata.normalize("NFC", w["text"].strip())
        text = ed.get("text") or apply_glossary(heard, glossary)
        if not ed.get("text") and text == heard and language == "bn":
            text = to_policy(heard, policy)
        text = fix_latin_vowel_sign(text)
        if not text:
            continue
        conf = float(w.get("conf", 1.0))
        edited = "text" in ed
        words.append(Word(id=wid, text=text, start=round(s, 3), end=round(e, 3), conf=round(conf, 3),
                          caption_start=round(cuts.map_time_nearest(ed["caption_start_src"]), 3) if "caption_start_src" in ed else None,
                          caption_end=round(cuts.map_time_nearest(ed["caption_end_src"]), 3) if "caption_end_src" in ed else None,
                          lang=detect_lang(text), flag="review" if (conf < 0.5 and not edited) else None,
                          cut=bool(ed.get("cut", False)), speaker=w.get("speaker")))
        prev_end = e
    return Transcript(language=language, words=words)


def _split_long(run: list[Word], max_words: int, max_seconds: float | None = None) -> list[list[Word]]:
    """Split a long run of words at its biggest pause (searched in the middle 40-60% so halves stay balanced), recursively.
    `max_seconds` (the reel look) also splits a run that is short in words but slow in time: a picture must not hold longer than that."""
    if len(run) <= max_words and not (max_seconds and len(run) >= 4 and run[-1].end - run[0].start > max_seconds):
        return [run]
    lo, hi = max(1, int(len(run) * 0.3)), max(2, int(len(run) * 0.7))
    best = max(range(lo, min(hi, len(run) - 1) + 1), key=lambda i: (run[i].start - run[i - 1].end) + (0.15 if run[i - 1].text.rstrip().endswith(SOFT) else 0.0)
               - (9.0 if run[i - 1].text.strip().rstrip(".").lower() in ABBREV else 0.0))          # never between "Mr." and "Rich"
    return _split_long(run[:best], max_words, max_seconds) + _split_long(run[best:], max_words, max_seconds)


SOFT = tuple(",;:—–")
# a full stop after these ends no sentence (the voice also pauses a little after them)
ABBREV = {"mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr", "mt", "vs", "etc", "e.g", "i.e", "u.s", "u.k", "inc", "co", "ltd", "no", "fig", "approx"}


def build_beats(tr: Transcript, max_words: int = 12, pause: float = 0.5, max_seconds: float | None = None) -> Beats:
    """Sentence-like groups of words: break on sentence punctuation and long pauses; long runs without either (the Bangla
    model emits no punctuation) are split at their biggest pause, never at an arbitrary word count."""
    ws = tr.kept()
    runs: list[list[Word]] = []
    cur: list[Word] = []
    for i, w in enumerate(ws):
        cur.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        gap = (nxt.start - w.end) if nxt else 99
        abbrev = w.text.strip().rstrip(".").lower() in ABBREV and w.text.rstrip().endswith(".")       # "Mr. Rich" is one name, not two sentences
        if nxt is None or (w.text.rstrip().endswith(SENTENCE_END) and not abbrev) or gap > (pause * 2.5 if abbrev else pause) or (nxt.speaker != w.speaker):
            runs.append(cur)
            cur = []
    groups = [g for r in runs for g in _split_long(r, max_words, max_seconds)]
    # merge one-word beats into a neighbour so scenes do not flicker
    merged: list[list[Word]] = []
    for g in groups:
        if merged and len(g) < 2 and len(merged[-1]) + len(g) <= max_words + 2 and merged[-1][-1].speaker == g[0].speaker:
            merged[-1].extend(g)
        else:
            merged.append(g)
    if len(merged) > 1 and len(merged[0]) < 2 and merged[0][0].speaker == merged[1][0].speaker:
        merged[1] = merged[0] + merged[1]
        merged.pop(0)
    beats = [Beat(id=f"b{i}", word_ids=[w.id for w in g], start=g[0].start, end=g[-1].end, text=" ".join(w.text for w in g), speaker=g[0].speaker)
             for i, g in enumerate(merged, 1)]
    return Beats(beats=beats)
