"""Search the visual library by meaning (embedding model) or, without the model, by keywords."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from .. import paths
from ..util import read_json
from . import emoji as emo
from .lexicon import Lexicon, norm


@lru_cache(maxsize=1)
def _docs() -> list[dict]:
    return read_json(paths.ICONS / "docs.json", []) or []


def _describe(vid: str) -> dict:
    if vid.startswith("emoji:"):
        key = vid[6:]
        if key.startswith("art-"):
            from .. import art

            return {"id": vid, "kind": "sticker", "emoji": "", "hex": key, "label": art.label(key), "label_bn": ""}
        e = emo.index().get(key, {})
        return {"id": vid, "kind": "sticker", "emoji": e.get("emoji", ""), "hex": key, "label": e.get("en", key), "label_bn": e.get("bn", "")}
    return {"id": vid, "kind": "icon", "label": vid.split(":", 1)[-1].replace("-", " ")}      # a bare name ("circle-help") is a Lucide icon


def svg_for(vid: str) -> dict:
    """What the Studio draws for a visual: {'svg': full colour markup} or {'inner': 24x24 line-icon markup}."""
    if vid.startswith("emoji:"):
        return {"svg": emo.svg(vid[6:]) or ""}
    from .icons import inner

    return {"inner": inner(vid) or ""}


def search(query: str, kind: Optional[str] = None, limit: int = 10) -> list[dict]:
    """kind: 'icon' (line icons), 'sticker' (colour emoji) or None. Blocked emoji never appear."""
    q = norm(query)
    if not q:
        return []
    lex = Lexicon.get()
    if re.search(r"[^\x00-\u024f]", q):  # not Latin script: translate (cached) so the English dictionary can answer
        from . import translate

        translate.prefetch([q])
    hits: list[str] = []
    from ..art import concepts

    if kind != "icon":                                      # drawn clipart whose name contains the query ("space" is not one, "galax" is)
        hits += [f"emoji:{k}" for k, (name, _) in concepts.KEYS.items() if len(q) >= 4 and (q in name.lower() or name.lower() in q)][:3]
    names = {q, q + "s", q + "es"} | ({q[:-1]} if q.endswith("s") else set()) | ({q[:-2]} if q.endswith("es") else set())
    for d in _docs():                                       # a picture literally called what was asked for ("grapes") beats any look-alike by meaning ("hyacinth")
        if (kind != "icon" and d["kind"] == "sticker" or kind != "sticker" and d["kind"] == "line") and str(d["en"]).split(";")[0].strip().lower() in names and d["id"] not in hits:
            hits.append(d["id"])
    head_docs = [d for d in _docs() if (kind != "icon" and d["kind"] == "sticker" or kind != "sticker" and d["kind"] == "line")      # "ball" -> "soccer ball", "bulb" -> "light bulb"
            and any(str(d["en"]).split(";")[0].strip().lower().endswith(" " + n) for n in names) and d["id"] not in hits]
    hits += [d["id"] for d in sorted(head_docs, key=lambda d: len(str(d["en"]).split(";")[0]))][:2]          # the plainest name first (soccer ball before person bouncing ball)
    m = lex.lookup(q)                                       # curated/dictionary answer first
    if m:
        for v in ((m.line if kind != "sticker" else None), (f"emoji:{m.sticker}" if m.sticker and kind != "icon" else None)):
            if v and v not in hits:
                hits.append(v)
    try:
        from .picker import _embedder

        emb = _embedder()
        if emb is not None and lex.ok:
            vec = emb.encode([q], prefix="query: ", max_len=24)[0]
            for vid, _, _ in lex.nearest(vec, limit * 2, "line" if kind == "icon" else "sticker" if kind == "sticker" else None):
                if vid not in hits:
                    hits.append(vid)
    except Exception:
        pass
    if len(hits) < limit:                                   # keyword fallback
        toks = set(re.findall(r"\w+", q))
        scored = []
        for d in _docs():
            if kind == "icon" and d["kind"] != "line" or kind == "sticker" and d["kind"] != "sticker":
                continue
            text = (d["en"] + " " + d["bn"]).lower()
            s = sum(1 for t in toks if t in text)
            if s:
                scored.append((-s, d["id"]))
        hits += [i for _, i in sorted(scored)[:limit] if i not in hits]
    out = []
    for v in hits:
        if v.startswith("emoji:") and not emo.emoji_key(v[6:]):
            continue
        out.append({**_describe(v), **svg_for(v)})
        if len(out) >= limit:
            break
    return out
