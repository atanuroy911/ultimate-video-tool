"""Cartoon 2: an AI redesigns each scene of the rule draft (the story engine's planner/llm.py, on our providers).

The AI never invents timing or words: per scene it receives the time window, the captions in it, the cast, the previous scene and the rule draft, and
returns {bg, elements, sfx?, tag?}. The answer is checked by the engine's validator and our schema; problems go back once for a repair; a scene that
still fails keeps its rule design. Works with whichever provider the chosen director runs on (local model, Claude on the server, an API).
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

from pathlib import Path
from ..house_rules import prompt as house_rules
from .plan import check_scene

SCHEMA = {"type": "object", "properties": {"bg": {"type": "object"}, "elements": {"type": "array", "items": {"type": "object"}},
                                           "sfx": {"type": "array"}, "tag": {"type": ["string", "null"]}}, "required": ["bg", "elements"]}

HOUSE_RULES = "\n## " + house_rules("story", start=11) + "\n"          # vt/house_rules.py: one list for every planner


def system_prompt(aspect: str = "9:16") -> str:
    text = (Path(__file__).with_name("scene_designer.md")).read_text(encoding="utf-8")         # the story engine's own designer prompt
    if aspect != "9:16":
        text += (f"\n## Frame\nThis video is {aspect}. The same 540 x 960 design is used, but only the band y 70-770 is visible and the backgrounds "
                 "are widened. Keep everything between y 120 and 720 and x 0 and 540.\n")
    return text + HOUSE_RULES


def scene_prompt(spec: dict, i: int) -> str:
    sc = spec["scenes"][i]
    caps = [c for c in spec["captions"] if c["s"] < sc["e"] and c["e"] > sc["s"]]
    cast = {k: {"name": v.get("name", ""), "female": bool(v.get("bun") or (v.get("lungi") and v.get("orna")))} for k, v in spec["characters"].items()}
    prev = spec["scenes"][i - 1] if i else None
    msg = {
        "scene_window": [sc["s"], sc["e"]],
        "captions": [{"s": c["s"], "e": c["e"], "text": re.sub(r"[{}\n]", " ", c["t"]), "speaker": c.get("who")} for c in caps],
        "cast": cast,
        "cast_ids": "use these ids in `char` (not the names): " + ", ".join(f"{k} = {v['name'] or k}" for k, v in cast.items()),
        "story_position": f'{100 * sc["s"] / spec["meta"]["total"]:.0f}%',
        "previous_scene": {"bg": prev["bg"], "element_types": [e["type"] for e in prev["elements"]]} if prev else None,
        "rule_engine_draft": {"bg": sc["bg"], "elements": sc["elements"]},
    }
    return "Design this scene. Improve on the draft if you can; keep what works.\n" + json.dumps(msg, ensure_ascii=False)


def refine(spec: dict, aspect: str = "9:16", progress: Optional[Callable[[float, str], None]] = None, provider=None) -> tuple[dict, int]:
    """Replace rule-made scene visuals with AI designs where the AI produced a valid scene. Returns (spec, scenes designed by the AI)."""
    from ..ai.providers import AIUnavailable, complete_json

    system = system_prompt(aspect)
    if provider is not None and hasattr(provider, "available") and not provider.available():
        raise AIUnavailable(f"{getattr(provider, 'name', 'the AI')} is not answering")
    names = {str(v.get("name", "")).lower(): k for k, v in spec["characters"].items() if v.get("name")}

    def repair(o):                                          # models often write the person's name where the cast id belongs
        for el in (o.get("elements") or []) if isinstance(o, dict) else []:
            if isinstance(el, dict) and el.get("char") not in spec["characters"] and str(el.get("char", "")).lower() in names:
                el["char"] = names[str(el["char"]).lower()]
        return o
    used = 0
    n = len(spec["scenes"])
    for i, sc in enumerate(spec["scenes"]):
        if progress:
            progress(i / max(1, n), f"Designing scene {i + 1} of {n}")
        s, e = sc["s"], sc["e"]
        try:
            out = complete_json(scene_prompt(spec, i), SCHEMA, system=system, provider=provider, retries=1, max_tokens=3000, timeout=180,
                                temperature=0.4, repair=repair, check=lambda o, s=s, e=e: [x for x in check_scene(o, s, e, spec["characters"]) if "outside" not in x])
        except Exception:                               # this scene keeps its rule design; the next one is tried
            continue
        used += 1
        sc["bg"] = out.get("bg") or sc["bg"]
        sc["elements"] = out["elements"]
        sc["note"] = "ai: " + sc.get("note", "")
        if out.get("sfx"):
            spec["sfx"] = [f for f in spec["sfx"] if not (s <= f[1] < e)] + [f for f in out["sfx"] if isinstance(f, list) and len(f) == 3]
        tag = " ".join(str(out.get("tag") or "").split())
        if tag and len(tag) <= 14 and len(tag.split()) <= 2:           # a label, not a sentence; otherwise the rule director's place/time label stays
            spec["tags"] = [t for t in spec["tags"] if not (t["s"] <= s < t["e"])] + [{"s": s, "e": e, "tag": tag}]
    spec["tags"].sort(key=lambda t: t["s"])
    spec["sfx"].sort(key=lambda f: f[1])
    return spec, used
