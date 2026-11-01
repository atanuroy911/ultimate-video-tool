"""Chooses, for every sentence, the word to illustrate and the visual that fits it in context.

score(word) = 0.45 * how strongly it was stressed  +  0.20 * how rare it is  +  0.35 * how well it can be pictured.
The visual comes from the dictionary (seed, WordNet, Bangla keywords) and, for unseen words or to settle an ambiguous sense,
from the embedding model comparing the word *and its sentence* against every icon. Recently used visuals are penalised so
neighbouring scenes look different.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .. import paths
from ..schema import Beats, Transcript, Word
from . import emoji as emo
from .emphasis import emphasis_scores
from .lexicon import BN_RE, MIN_Z, MIN_Z_EMBED, Lexicon, Match, bn_variants, norm

BN_STOP = set("""এই এটা এটাকে এটি সেটা সেটাই সেটি যে যেটা যেটি কি কী না আর ও এবং তো হয় হলো হল হবে হচ্ছে হয়ে করে করা করতে করছে করেন করি একটা একটি এক একটু
তখন তারপর এরপর কিন্তু তাহলে তবে যদি থেকে জন্য দিয়ে দিয়া বলে বলি বলেন আছে নেই নাই তার তাদের তাকে তাঁর আমার আমাকে আপনার আপনি আমি আমরা তুমি তোমার তোমাকে সে ওরা
সেই ওই ঐ দিকে দিকেই ব্যাপার কেন কীভাবে কিভাবে যখন কত কতো খুব পর আগে সাথে সঙ্গে মধ্যে মতো মত এখন এখানে সেখানে সব সবকিছু সবাই কিছু কোনো কোন কেউ কারও যাও যায় যেতে গিয়ে গেল গেলে
দিল দিলে দিতে নিয়ে নিল নিতে নেব দেব দেখা বা অথবা তাই তাই তাহা এসে আসে আসা এল থাকে থাকবে থাকা ছিল ছিলাম আরও আরো শুধু শুধুমাত্র এমনি""".split())
EN_STOP = set("""the a an and or but if so to of in on at by for with from as is are was were be been being it its this that these those i you he she we they me him her us them
my your his our their not no yes do does did done have has had will would can could should may might just very really also then than there here what which who when where why how
all any some more most other such only own same too up down out over under again further once about into through during before after above below between
said say says saying went go goes going come came comes get got gets make made makes let lets one two upon day next told tell asked ask gave give gives take took takes
someone everyone anyone everything something nothing anything another many much every each both even ever never always already still yet now soon
like back away around together while because until since though although however thing things way ways kind sort bit lot lots""".split())


STRONG_Z = 7.0                 # a dictionary match this sure ("lazy" -> sleepy face) is shown even for a non-noun


@dataclass
class Pick:
    beat: str
    word_id: str
    text: str
    kind: str                      # 'sticker' | 'icon' | 'text'
    line: Optional[str] = None
    sticker: Optional[str] = None
    z: float = 0.0
    score: float = 0.0
    emphasis: float = 0.5
    source: str = ""
    alternatives: list[dict] = field(default_factory=list)
    extras: list[dict] = field(default_factory=list)      # other picturable words of the same sentence (word_id, text, line, sticker)


def _zipf(word: str) -> float:
    try:
        from wordfreq import zipf_frequency

        return zipf_frequency(word, "bn" if BN_RE.search(word) else "en")
    except Exception:
        return 3.0


def is_content(w: Word) -> bool:
    t = norm(w.text)
    if len(t) < (2 if BN_RE.search(t) else 3) or t.isdigit() or re.fullmatch(r"[\d০-৯.,%]+", t):
        return False
    if t in BN_STOP or t in EN_STOP:
        return False
    return not (_zipf(t) > 6.4)


def rarity(word: str) -> float:
    z = _zipf(norm(word))
    return 0.7 if z == 0 else float(np.clip((6.6 - z) / 4.2, 0.0, 1.0))


def _embedder():
    """The embedding model if it is downloaded (planning works without it, with a smaller vocabulary)."""
    if not (paths.MODELS / "e5-small" / "model.safetensors").exists():
        return None
    try:
        from .embed import Embedder

        return Embedder.get()
    except Exception:
        return None


def pick_visuals(tr: Transcript, beats: Beats, audio: Optional[Path] = None, *, use_embedder: bool = True) -> dict[str, Pick]:
    lex = Lexicon.get()
    words = {w.id: w for w in tr.kept()}
    emph = emphasis_scores(audio, list(words.values()))
    emb = _embedder() if (use_embedder and lex.ok) else None

    # candidates per beat
    cand: dict[str, list[Word]] = {b.id: [words[i] for i in b.word_ids if i in words and is_content(words[i])] for b in beats.beats}
    matches: dict[str, Optional[Match]] = {}
    need: list[Word] = []
    pinned: dict[str, Match] = {}
    for b in beats.beats:                                       # two-word ideas ("black hole", "solar system"): the pair is drawn once, on its second word
        seq = [words[i] for i in b.word_ids if i in words]
        for w1, w2 in zip(seq, seq[1:]):
            m2 = lex.art(f"{w1.text} {w2.text}")
            if m2:
                pinned[w2.id] = m2
                cand[b.id] = [w for w in cand[b.id] if w.id != w1.id]
                if all(w.id != w2.id for w in cand[b.id]):
                    cand[b.id].append(w2)
    if use_embedder:                                            # Bangla etc.: ask Google Translate once for every unknown word
        from . import translate

        translate.prefetch([v for ws in cand.values() for w in ws if BN_RE.search(w.text) and lex.bn(w.text) is None
                            for v in bn_variants(norm(w.text))[:2]])
    for ws in cand.values():
        for w in ws:
            m = pinned.get(w.id) or lex.lookup(w.text)
            matches[w.id] = m
            if m is None or not m.usable():
                need.append(w)
    vecs: dict[str, np.ndarray] = {}
    if emb is not None and need:                                # unseen words (typically Bangla): look up by meaning
        Q = emb.encode([norm(w.text) for w in need], prefix="query: ", max_len=16)
        for w, q in zip(need, Q):
            vecs[w.id] = q
            m = lex.from_vector(w.text, q)
            if m:
                matches[w.id] = m
    sent_vec: dict[str, np.ndarray] = {}
    if emb is not None:
        S = emb.encode([b.text for b in beats.beats], prefix="query: ", max_len=64)
        sent_vec = {b.id: S[i] for i, b in enumerate(beats.beats)}

    from . import terms as T

    topics = T.topic_counts(w.text for w in words.values())
    recent: list[str] = []
    picks: dict[str, Pick] = {}
    for b in beats.beats:
        scored = []
        for w in cand[b.id]:
            m = matches.get(w.id)
            # context: settle ambiguous senses by comparing word + sentence with every icon
            if emb is not None and m is not None and m.source != "seed" and b.id in sent_vec:
                wv = vecs.get(w.id)
                if wv is None:
                    wv = emb.encode([norm(w.text)], prefix="query: ", max_len=16)[0]
                q = wv + 0.5 * sent_vec[b.id]
                q = q / (np.linalg.norm(q) + 1e-9)
                m2 = lex.from_vector(w.text, q)
                if m2 and m2.best >= max(m.best + 0.3, MIN_Z_EMBED):
                    m = m2
            icon = 0.0
            if m and m.usable():
                icon = 1.0 if m.source == "seed" else float(np.clip((m.best - 3.5) / 4.5, 0.0, 1.0))
            e = emph.get(w.id, 0.5)
            key = T.is_key_term(w.text, topics)
            s = 0.40 * e + 0.15 * rarity(w.text) + 0.30 * icon + 0.25 * T.score(w.text, topics)
            if not key and not (m and m.usable() and (m.source == "seed" or m.best >= STRONG_Z)):
                s -= 0.35                                       # "fine", "leave", "interesting": not worth a picture or a headline
            vid = (m.sticker or m.line or "") if m else ""
            if vid.startswith("art-"):                          # drawn for exactly this idea: it beats a vaguely related emoji
                s += 0.3
            if vid and vid in recent[-6:]:
                s -= 0.25
            scored.append((s, w, m, e))
        if not scored:
            continue
        scored.sort(key=lambda t: -t[0])
        s, w, m, e = scored[0]
        usable = bool(m and m.usable())
        if not T.is_key_term(w.text, topics) and not (usable and (m.source == "seed" or m.best >= STRONG_Z)):
            continue                                            # nothing worth showing in this sentence: the scene builder decides
        kind = "text"
        if usable:
            kind = "sticker" if (m.sticker and m.z_sticker >= max(MIN_Z, m.z_line - 0.4)) else ("icon" if (m.line and m.z_line >= MIN_Z) else ("sticker" if m.sticker else "text"))
        picks[b.id] = Pick(b.id, w.id, w.text.strip(" ,.।?!"), kind, m.line if (m and usable) else None, m.sticker if (m and usable) else None,
                           (m.best if m else 0.0), s, e, m.source if m else "",
                           [{"word": x[1].text.strip(" ,.।?!"), "score": round(x[0], 3), "emphasis": round(x[3], 2),
                             "visual": ((x[2].sticker and f"emoji:{x[2].sticker}") or x[2].line) if x[2] else None} for x in scored[1:4]])
        vid = (m.sticker if kind == "sticker" else m.line) if usable else ""
        if vid:
            recent.append(vid)
        seen = {vid}
        for x in scored[1:]:                                     # the sentence's other picturable words, best first
            xm = x[2]
            if not (xm and xm.usable() and (xm.sticker or xm.line)) or len(picks[b.id].extras) >= 3:
                continue
            if xm.source != "seed" and xm.best < STRONG_Z and not T.is_key_term(x[1].text, topics):    # an extra picture must be of a real thing or key idea
                continue
            xv = xm.sticker or xm.line
            if xv in seen or x[3] < 0.2:
                continue
            seen.add(xv)
            picks[b.id].extras.append({"word_id": x[1].id, "text": x[1].text.strip(" ,.।?!"), "line": xm.line if not xm.sticker else None, "sticker": xm.sticker})
    return picks
