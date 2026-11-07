"""Small, grounded library menus for planning and the director's one revision."""
from __future__ import annotations

import json
from types import SimpleNamespace

from .lexicon import norm

MAX_TERMS = 6
MAX_OPTIONS = 3
MAX_PROMPT = 12_000
MAX_GROUPS = 24


def for_text(text: str) -> list[dict]:
    from .picker import is_content
    from .search import search

    choices, seen = [], set()
    for token in text.split():
        word = norm(token)
        if word in seen or not is_content(SimpleNamespace(text=word)):
            continue
        seen.add(word)
        try:
            # Prompt construction must not start a model or make a translation
            # request. Curated dictionary and literal keyword matches still use
            # the same real visual library as the Studio's search.
            hits = search(word, limit=MAX_OPTIONS, use_embedder=False, use_translation=False)
        except Exception:
            hits = []
        options = []
        for hit in hits:
            visual_id = hit.get("id")
            if not isinstance(visual_id, str):
                continue
            sticker = visual_id.startswith("emoji:")
            options.append({"type": "sticker" if sticker else "icon", "field": "emoji" if sticker else "name",
                            "value": visual_id[6:] if sticker else visual_id, "label": str(hit.get("label") or visual_id)[:80]})
        if options:
            choices.append({"word": word, "options": options[:MAX_OPTIONS]})
        if len(seen) >= MAX_TERMS:
            break
    return choices


def prompt(groups: list[tuple[str, str]]) -> str:
    rows, used = [], 0
    for name, text in groups[:MAX_GROUPS]:
        options = for_text(text)
        if not options:
            continue
        row = json.dumps({"scene_or_beat": name, "choices": options}, ensure_ascii=False)
        if used + len(row) > MAX_PROMPT:
            break
        rows.append(row)
        used += len(row)
    if not rows:
        return ""
    return ("REAL VISUAL CHOICES for the spoken words below. These are library matches, not instructions from the source. "
            "Choose a label that actually means the spoken word; copy its field and value exactly instead of guessing an emoji code. "
            "If none fits the sentence, use the spoken word as text. These are suggestions, not changes to the plan.\n" + "\n".join(rows))
