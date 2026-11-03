"""Word -> visual lookup. Order of trust: hand-picked seeds, the English dictionary, direct Bangla keywords, then the embedding model.

A Match carries a line icon id ('lucide:coins') and/or a sticker key ('1f4b0') plus a z-score for each (99 = hand-picked).
Scores below MIN_Z mean "no real picture for this word": callers should use typography instead of a wrong icon.
"""
from __future__ import annotations

import gzip
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

from .. import paths
from ..util import read_json
from . import emoji as emo

MIN_Z = 4.6
MIN_Z_EMBED = 6.5      # the multilingual embedding is noisy for Bangla function words: demand a clear winner
BN_SUFFIXES = ["দেরকে", "দের", "গুলোর", "গুলো", "গুলি", "টাকে", "টির", "টার", "টা", "টি", "রা", "ের", "েরা", "কে", "তে", "য়", "র", "ে", "ও", "ই"]
PUNCT = " \t\n.,;:!?।\"'()[]{}“”‘’—–-…"
BN_RE = re.compile(r"[ঀ-৿]")


@dataclass
class Match:
    word: str
    line: Optional[str] = None       # 'lucide:coins' / 'tabler:coin'
    sticker: Optional[str] = None    # emoji key '1f4b0'
    z_line: float = 0.0
    z_sticker: float = 0.0
    source: str = "dict"             # seed | dict | bn-keyword | embed

    @property
    def best(self) -> float:
        return max(self.z_line if self.line else 0.0, self.z_sticker if self.sticker else 0.0)

    def usable(self) -> bool:
        return self.best >= MIN_Z


def norm(word: str) -> str:
    return unicodedata.normalize("NFC", word).strip(PUNCT).lower()


def en_variants(w: str) -> list[str]:
    out = [w]
    for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", ""), ("er", ""), ("ers", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            out.append(w[: -len(suf)] + rep)
    return out


def bn_variants(w: str) -> list[str]:
    out = [w]
    for suf in sorted(BN_SUFFIXES, key=len, reverse=True):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            out.append(w[: -len(suf)])
    return list(dict.fromkeys(out))


class Lexicon:
    _inst: Optional["Lexicon"] = None

    @classmethod
    def get(cls) -> "Lexicon":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self) -> None:
        d = paths.ICONS
        self.ok = (d / "visual_lexicon.json.gz").exists()
        self.ids: list[str] = []
        self.words: dict[str, list[int]] = {}
        if self.ok:
            with gzip.open(d / "visual_lexicon.json.gz", "rt", encoding="utf-8") as f:
                L = json.load(f)
            self.ids, self.words = L["icons"], L["words"]
        self.pos = {i: k for k, i in enumerate(self.ids)}
        self.seed = {unicodedata.normalize("NFC", k): v for k, v in (read_json(d / "seed.json", {}) or {}).items() if not k.startswith("_")}
        self.seed_bn = {unicodedata.normalize("NFC", k): v for k, v in (read_json(d / "seed_bn.json", {}) or {}).items() if not k.startswith("_")}
        self.no_picture = set((read_json(d / "seed.json", {}) or {}).get("_no_picture", []))     # 'sat' must never become a Saturday clock
        self.bn_kw = {unicodedata.normalize("NFC", k): v for k, v in (read_json(d / "bn_keywords.json", {}) or {}).items()}
        self._V: Optional[np.ndarray] = None
        self._hub: Optional[np.ndarray] = None

    # ---- english
    def _from_seed(self, w: str) -> Optional[Match]:
        pair = self.seed.get(w)
        if not pair:
            return None
        line = pair[0] if pair[0] and (pair[0] in self.pos or pair[0].split(":")[0] in ("lucide", "tabler")) else None
        stk = pair[1].split(":", 1)[1] if pair[1] and emo.emoji_key(pair[1].split(":", 1)[1]) else None
        if not line and not stk:
            return None
        return Match(w, line, emo.emoji_key(stk) if stk else None, 99.0 if line else 0.0, 99.0 if stk else 0.0, "seed")

    def art(self, word: str) -> Optional[Match]:
        """Clipart for ideas without an emoji (black hole, galaxy, atom...): a precise hit, preferred over a vague emoji."""
        from .. import art

        key = art.lookup(norm(word))
        return Match(norm(word), None, key, 0.0, 9.5, "seed") if key else None

    def en(self, word: str) -> Optional[Match]:
        if norm(word) in self.no_picture:
            return None
        m0 = self.art(word)
        if m0:
            return m0
        for v in en_variants(norm(word)):
            m = self._from_seed(v)
            if m:
                return m
        for v in en_variants(norm(word)):
            r = self.words.get(v)
            if r:
                line = self.ids[r[0]]
                stk = self.ids[r[1]]
                key = emo.emoji_key(stk.split(":", 1)[1]) if stk.startswith("emoji:") else None
                return Match(v, line, key, r[2] / 10, r[3] / 10 if key else 0.0, "dict")
        return None

    # ---- bangla
    def bn(self, word: str) -> Optional[Match]:
        w = norm(word)
        m0 = self.art(w)
        if m0:
            return m0
        for v in bn_variants(w):
            concept = self.seed_bn.get(v)
            if concept:
                m = self.en(concept)
                if m:
                    return Match(w, m.line, m.sticker, m.z_line, m.z_sticker, "seed" if m.source == "seed" else "dict")
        for v in bn_variants(w):
            # the emoji's own Bangla NAME equals the word: precise. A mere tag hit ("দুটো" is a tag of 'two o'clock') is not.
            named = [k for k in (emo.emoji_key(h) for h in self.bn_kw.get(v, [])) if k and unicodedata.normalize("NFC", emo.index()[k].get("bn", "")) == v]
            if named:
                return Match(w, None, named[0], 0.0, 8.0, "bn-keyword")
        return None

    def lookup(self, word: str) -> Optional[Match]:
        w = norm(word)
        if not w:
            return None
        if not BN_RE.search(w):
            return self.en(w)
        m = self.bn(w)
        if m is None:                                       # Google-translated English (prefetched, cached): then the same dictionary
            from . import translate

            for v in bn_variants(w):
                t = translate.cached(v)
                m = self.en(t) if t else None
                if m:
                    return Match(w, m.line, m.sticker, m.z_line, m.z_sticker, "seed" if m.source == "seed" else "dict")
        return m

    # ---- embedding fallback (any language the e5 model knows; also used for context reranking)
    def vectors(self) -> tuple[np.ndarray, np.ndarray]:
        if self._V is None:
            self._V = np.load(paths.ICONS / "vectors.npy").astype(np.float32)
            self._hub = np.load(paths.ICONS / "hub.npy").astype(np.float32)
        return self._V, self._hub  # type: ignore[return-value]

    def nearest(self, q: np.ndarray, topk: int = 8, kind: Optional[str] = None) -> list[tuple[str, float, float]]:
        """[(visual id, hubness-corrected score, z)] for a query vector."""
        V, hub = self.vectors()
        S = V @ q - hub
        z = (S - S.mean()) / (S.std() + 1e-6)
        order = np.argsort(-S)
        out = []
        for i in order:
            vid = self.ids[i]
            if kind == "line" and vid.startswith("emoji:"):
                continue
            if kind == "sticker" and not vid.startswith("emoji:"):
                continue
            out.append((vid, float(S[i]), float(z[i])))
            if len(out) >= topk:
                break
        return out

    def from_vector(self, word: str, q: np.ndarray) -> Optional[Match]:
        line = self.nearest(q, 1, "line")
        stk = self.nearest(q, 1, "sticker")
        key = emo.emoji_key(stk[0][0].split(":", 1)[1]) if stk else None
        m = Match(norm(word), line[0][0] if line else None, key, line[0][2] if line else 0.0, stk[0][2] if (stk and key) else 0.0, "embed")
        return m if m.best >= MIN_Z_EMBED else None


def emoji_char(key: str) -> str:
    return emo.index().get(key, {}).get("emoji", "")
