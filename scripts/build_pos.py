"""Build design/icons/pos.json.gz: for common English words, how often each is a noun / verb / adjective (WordNet sense counts).

Used to pick key terms for on-screen keywords (nouns and noun-like terms beat "fine", "leave", "close"). WordNet is (c) Princeton University,
free to use and redistribute (see design/icons/LICENSE.txt). Run once: python scripts/build_pos.py"""
import gzip
import json
from collections import defaultdict
from pathlib import Path

import nltk
from wordfreq import zipf_frequency

try:
    from nltk.corpus import wordnet as wn
    wn.synsets("dog")
except LookupError:
    nltk.download("wordnet", quiet=True)
    from nltk.corpus import wordnet as wn

out = defaultdict(lambda: [0.0, 0.0, 0.0])
IDX = {"n": 0, "v": 1, "a": 2, "s": 2, "r": None}
for syn in wn.all_synsets():
    i = IDX[syn.pos()]
    if i is None:
        continue
    for lem in syn.lemmas():
        w = lem.name().lower()
        if not w.isalpha():
            continue
        out[w][i] += 1.0 + 3.0 * lem.count()          # sense frequency from tagged text counts much more than a rare sense
keep = {w: [round(x / sum(v), 2) for x in v] for w, v in out.items() if zipf_frequency(w, "en") >= 1.5 and sum(v) > 0}
p = Path(__file__).resolve().parents[1] / "design" / "icons" / "pos.json.gz"
with gzip.open(p, "wt", encoding="utf-8") as f:
    json.dump(keep, f, separators=(",", ":"))
print(len(keep), "words ->", p, p.stat().st_size // 1024, "KB")
