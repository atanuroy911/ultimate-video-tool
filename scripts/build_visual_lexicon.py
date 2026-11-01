"""Builds the visual dictionary: every English dictionary word (WordNet, ~145k lemmas) -> its best line icon and best sticker.

    python scripts/build_visual_lexicon.py

Inputs : design/icons/docs.json + emoji_index.json (renderer/scripts/build-icons.mjs), seed.json (hand-picked concepts),
         the e5 embedding model (downloaded on first use).
Outputs: design/icons/vectors.npy + ids.json      icon embeddings (planning time: Bangla and unseen words)
         design/icons/visual_lexicon.json.gz      word -> [line icon, sticker, line z*10, sticker z*10]
         design/icons/bn_keywords.json            Bangla keyword -> emoji (from the Bengali emoji annotations)

Quality measures: brand logos, flags, symbols and letter/number glyphs are excluded; matches are hubness-corrected (a few generic
icons such as "quote" or "import" otherwise attract thousands of words); queries are enriched with synonyms; seed.json overrides
the automatic choice for common concepts. The z-score says how much better the best icon is than a typical one for that word.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vt.visuals.embed import Embedder  # noqa: E402
from vt.visuals.emoji import BLOCKED  # noqa: E402

ICONS = ROOT / "design" / "icons"
WORD_RE = re.compile(r"^[a-z][a-z' -]{1,30}$")
NOISE_LINE = re.compile(r"^(tabler|lucide):(brand-|letter-|square-letter|alphabet|number-|square-number|circle-number|flag-|hexagon-letter|hexagon-number|"
                        r"square-rounded-letter|square-rounded-number|currency-(?!dollar|euro|pound|yen|taka|rupee|bitcoin))")
NOISE_EMOJI_GROUPS = {8, 9}          # symbols, flags
HUB_LAMBDA = 1.0


def main() -> None:
    docs = json.loads((ICONS / "docs.json").read_text(encoding="utf-8"))
    eidx = json.loads((ICONS / "emoji_index.json").read_text(encoding="utf-8"))
    seed_ids = {i for v in json.loads((ICONS / "seed.json").read_text(encoding="utf-8")).values() if isinstance(v, list) for i in v if i}
    keep = []
    for d in docs:
        if NOISE_LINE.match(d["id"]) or (d["id"].startswith("emoji:") and d["id"][6:] in BLOCKED):
            continue
        if d["id"].startswith("emoji:") and eidx[d["id"][6:]]["group"] in NOISE_EMOJI_GROUPS and d["id"] not in seed_ids:
            continue          # symbols/flags stay out unless the seed table names them (e.g. warning sign for "problem")
        keep.append(d)
    print(f"{len(docs)} visuals, {len(keep)} after removing brands/flags/symbols/glyphs")
    docs = keep
    ids = [d["id"] for d in docs]
    pos = {i: k for k, i in enumerate(ids)}
    kinds = np.array([0 if d["kind"] == "line" else 1 for d in docs])
    emb = Embedder.get()
    print(f"embedding on {emb.device}")
    texts = [d["en"] + ((" | " + d["bn"]) if d["bn"] else "") for d in docs]
    V = emb.encode(texts, prefix="passage: ", max_len=64)
    np.save(ICONS / "vectors.npy", V.astype(np.float16))
    (ICONS / "ids.json").write_text(json.dumps(ids), encoding="utf-8")

    import nltk
    from nltk.corpus import wordnet as wn
    from wordfreq import top_n_list

    nltk.download("wordnet", quiet=True)
    words, queries = [], []
    for name in sorted(wn.all_lemma_names()):
        w = name.replace("_", " ").lower()
        if not WORD_RE.match(w):
            continue
        syn = wn.synsets(name)
        words.append(w)
        if syn:
            s0 = syn[0]
            others = [l.replace("_", " ") for l in s0.lemma_names() if l.lower() != name.lower()][:3]
            queries.append(f"{w} ({', '.join(others)}): {s0.definition()[:100]}" if others else f"{w}: {s0.definition()[:110]}")
        else:
            queries.append(w)
    print(f"{len(words)} dictionary words")

    # hubness: how strongly each icon is attracted by ordinary words (mean of its top-20 similarities to a common-word sample)
    wi = {w: k for k, w in enumerate(words)}
    common = [w for w in top_n_list("en", 40000) if w in wi][:20000]
    sample = [queries[wi[w]] for w in common]
    Qs = emb.encode(sample, prefix="query: ", max_len=48)
    S0 = Qs @ V.T
    hub = np.sort(S0, axis=0)[-20:].mean(axis=0)            # per icon
    hub = hub - hub.mean()
    np.save(ICONS / "hub.npy", hub.astype(np.float32))
    print(f"hubness estimated from {len(sample)} common words (spread {hub.min():.3f}..{hub.max():.3f})")

    line_idx, st_idx = np.where(kinds == 0)[0], np.where(kinds == 1)[0]
    lex: dict[str, list[int]] = {}
    t0 = time.time()
    B = 4096
    for i in range(0, len(words), B):
        Q = emb.encode(queries[i: i + B], prefix="query: ", max_len=56)
        S = Q @ V.T - HUB_LAMBDA * hub[None, :]
        mu, sd = S.mean(1, keepdims=True), S.std(1, keepdims=True) + 1e-6
        Z = (S - mu) / sd
        for k, w in enumerate(words[i: i + B]):
            bl = line_idx[int(np.argmax(S[k, line_idx]))]
            bs = st_idx[int(np.argmax(S[k, st_idx]))]
            lex[w] = [int(bl), int(bs), int(round(float(Z[k, bl]) * 10)), int(round(float(Z[k, bs]) * 10))]
        if (i // B) % 10 == 0:
            print(f"  {min(i + B, len(words))}/{len(words)}  {time.time() - t0:.0f}s", flush=True)

    # hand-picked concepts win (z-score 99 = certain)
    seed = json.loads((ICONS / "seed.json").read_text(encoding="utf-8"))
    missing = []
    for w, pair in seed.items():
        if w.startswith("_"):
            continue
        cur = lex.get(w, [0, 0, 0, 0])
        line = pos.get(pair[0]) if pair[0] else None
        stk = pos.get(pair[1]) if pair[1] else None
        if pair[0] and line is None or pair[1] and stk is None:
            missing.append((w, pair))
        lex[w] = [line if line is not None else cur[0], stk if stk is not None else cur[1],
                  99 if line is not None else cur[2], 99 if stk is not None else cur[3]]
    if missing:
        print("seed entries with unknown ids:", missing[:12], f"({len(missing)} total)")

    with gzip.open(ICONS / "visual_lexicon.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"v": 2, "icons": ids, "words": lex}, f, ensure_ascii=False, separators=(",", ":"))

    # Bangla keywords straight from the Bengali emoji annotations: exact keyword hits are very precise
    bn: dict[str, list[str]] = {}
    for hexcode, e in eidx.items():
        if e["group"] in NOISE_EMOJI_GROUPS or hexcode in BLOCKED:
            continue
        toks = [(t, 0) for t in re.split(r"[\s,;]+", e["bn"]) if t] + [(t, 1) for t in e["bn_tags"] for t in re.split(r"[\s,;]+", t) if t]
        for t, kind in toks:
            lst = bn.setdefault(t, [])
            if hexcode not in lst:
                lst.insert(0, hexcode) if kind == 0 else lst.append(hexcode)
    (ICONS / "bn_keywords.json").write_text(json.dumps({k: v[:8] for k, v in bn.items()}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"lexicon: {len(lex)} words ({(ICONS / 'visual_lexicon.json.gz').stat().st_size / 1e6:.1f} MB), {len(bn)} Bangla keywords")


if __name__ == "__main__":
    main()
