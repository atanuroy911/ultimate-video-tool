"""Which sentences carry the talk: graph centrality over a transcript, and a diverse pick from the ranked list.

Two classic, training-free algorithms, both language-agnostic (Bangla and English tokens alike):

* **LexRank** (Erkan & Radev, JAIR 2004, arXiv 1109.2128): sentences are nodes, edges weigh their TF-IDF cosine similarity,
  and importance is the stationary distribution of a random walk over that graph (the eigenvector centrality that TextRank,
  Mihalcea & Tarau 2004, also uses). A sentence many others resemble is central; a lone aside is not. Used by `vt/tighten.py`
  (what may be dropped) and `vt/shorts` (which windows are information-dense, the transcript-saliency reward of
  arXiv 2505.23268).
* **Maximal Marginal Relevance** (Carbonell & Goldstein, SIGIR 1998): pick the next item that is most relevant *and* least like
  what is already picked, `λ·rel − (1−λ)·max sim(picked)`. Used to choose shorts that do not all tell the same moment.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

TOKEN = re.compile(r"[\wঀ-৿']+", re.UNICODE)
# words so common they say nothing about a sentence's topic (a tiny list; TF-IDF does the rest)
STOP = set("the a an and or but of to in on at for with is are was were be been it this that i you he she we they my your "
           "so if then than as not no do did does have has had will would can could just very".split()) | \
       set("এই সেই আর ও এবং কিন্তু যে যা তা তার আমি তুমি সে আমরা তারা হয় হলো ছিল করে না কি একটা একটি".split())


# Bangla case endings and particles, stripped so "নেকড়ে" and "নেকড়ের" count as the same word (a light stemmer; longest first)
BANGLA_SUFFIXES = sorted(["গুলোর", "গুলো", "গুলি", "দের", "কে", "তে", "ের", "টার", "টা", "টি", "খানা", "রা", "য়", "র", "ে"], key=len, reverse=True)


def stem(token: str) -> str:
    if token and "ঀ" <= token[0] <= "৿":
        for suffix in BANGLA_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                return token[: -len(suffix)]
    return token


def tokens(text: str) -> list[str]:
    return [stem(t.lower()) for t in TOKEN.findall(text or "") if t.lower() not in STOP and len(t) > 1]


def tfidf_vectors(sentences: Sequence[str]) -> list[dict[str, float]]:
    docs = [Counter(tokens(s)) for s in sentences]
    n = max(1, len(docs))
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    out = []
    for d in docs:
        vec = {w: (1 + math.log(c)) * math.log((n + 1) / (df[w] + 0.5)) for w, c in d.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        out.append({w: v / norm for w, v in vec.items()})
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(w, 0.0) for w, v in a.items())


def similarity_matrix(sentences: Sequence[str]) -> list[list[float]]:
    vecs = tfidf_vectors(sentences)
    n = len(vecs)
    return [[1.0 if i == j else cosine(vecs[i], vecs[j]) for j in range(n)] for i in range(n)]


def lexrank(sentences: Sequence[str], damping: float = 0.85, iterations: int = 60) -> list[float]:
    """Centrality of every sentence, scaled so the mean is 1.0 (continuous LexRank: weighted edges, no threshold).
    One sentence, or sentences with no words in common, all score 1.0."""
    n = len(sentences)
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    sim = similarity_matrix(sentences)
    rows = []
    for i in range(n):
        total = sum(sim[i][j] for j in range(n) if j != i)
        rows.append([0.0 if j == i or total == 0 else sim[i][j] / total for j in range(n)])
    score = [1.0 / n] * n
    for _ in range(iterations):
        new = [(1 - damping) / n + damping * sum(score[j] * rows[j][i] for j in range(n)) for i in range(n)]
        if max(abs(a - b) for a, b in zip(new, score)) < 1e-6:
            score = new
            break
        score = new
    mean = sum(score) / n
    return [s / mean if mean else 1.0 for s in score]


def mmr_select(relevance: Sequence[float], similarity: Sequence[Sequence[float]], k: int, lam: float = 0.7) -> list[int]:
    """Indices of the k items that are most relevant and least alike (Carbonell & Goldstein). `similarity[i][j]` in 0..1."""
    n = len(relevance)
    if n == 0 or k <= 0:
        return []
    top = max(relevance) or 1.0
    rel = [r / top for r in relevance]
    picked: list[int] = []
    while len(picked) < min(k, n):
        best, best_score = -1, -1e9
        for i in range(n):
            if i in picked:
                continue
            redundancy = max((similarity[i][j] for j in picked), default=0.0)
            score = lam * rel[i] - (1 - lam) * redundancy
            if score > best_score:
                best, best_score = i, score
        picked.append(best)
    return picked
