"""Component catalogue: what the planner (Claude over MCP, or the rule planner) may use.
Generated from the pydantic element models so validation, forms and prompts never drift apart."""
from __future__ import annotations

import inspect
from functools import lru_cache

from .. import paths
from ..schema import ELEMENT_MODELS, LAYOUTS, TRANSITIONS
from ..util import read_json
from .element_library import library_info

# One valid example per element (at_word values are placeholders replaced in the prompt).
EXAMPLES: dict[str, dict] = {
    "shape": {"type": "shape", "shape": "rectangle", "color": "#6366f1", "label": "", "width": 0.65, "rounded": True, "at_word": "w1"},
    "title": {"type": "title", "text": "ইয়েল্ড", "at_word": "w1"},
    "value_card": {"type": "value_card", "value": "৳১০০", "label": "দোকানের দাম", "at_word": "w7"},
    "big_number": {"type": "big_number", "value": "৪", "unit": "%", "label": "বছরে আয়", "at_word": "w18"},
    "arrow": {"type": "arrow", "direction": "down", "label": "", "at_word": "w9"},
    "icon_row": {"type": "icon_row", "icon": "coin", "count": 3, "label": "বছরে ভাড়া", "at_word": "w12"},
    "tag": {"type": "tag", "text": "৪ = গ্রস", "at_word": "w14"},
    "compare": {"type": "compare", "left": {"title": "গ্রস", "value": "৪%"}, "right": {"title": "নেট", "value": "৩%"}, "verdict": "আসল লাভ নেট", "at_word": "w27"},
    "list": {"type": "list", "items": ["ভাড়া", "খরচ", "লাভ"], "at_word": "w5"},
    "equation": {"type": "equation", "parts": [{"text": "আয়"}, {"text": "−"}, {"text": "খরচ"}, {"text": "="}, {"text": "লাভ", "kind": "res"}], "at_word": "w21"},
    "quote": {"type": "quote", "text": "যেটা পকেটে থাকে সেটাই আসল", "at_word": "w24"},
    "bar_chart": {"type": "bar_chart", "bars": [{"label": "গ্রস", "value": 4, "display": "৪%"}, {"label": "নেট", "value": 3, "display": "৩%"}], "at_word": "w18"},
    "icon": {"type": "icon", "name": "piggy-bank", "label": "সঞ্চয়", "at_word": "w3"},
    "keyword": {"type": "keyword", "text": "পাথর", "emoji": "1faa8", "style": "underline", "at_word": "w12"},
    "sticker": {"type": "sticker", "emoji": "1f4b0", "label": "টাকা", "at_word": "w8"},
    "ring": {"type": "ring", "value": 72, "label": "সন্তুষ্ট গ্রাহক", "at_word": "w6"},
    "line_chart": {"type": "line_chart", "points": [{"label": "২০২০", "value": 10}, {"label": "২০২২", "value": 18}, {"label": "২০২৪", "value": 35}], "unit": "%", "label": "বৃদ্ধি", "at_word": "w9"},
    "steps": {"type": "steps", "items": [{"title": "লিখুন", "detail": "স্ক্রিপ্ট দিন"}, {"title": "বাছুন", "detail": "স্টাইল ঠিক করুন"}, {"title": "তৈরি", "detail": "ভিডিও পান"}], "at_word": "w3"},
    "timeline": {"type": "timeline", "events": [{"when": "২০১০", "what": "শুরু"}, {"when": "২০১৫", "what": "প্রথম লাভ"}, {"when": "২০২৪", "what": "দেশজুড়ে"}], "at_word": "w2"},
    "definition": {"type": "definition", "term": "ইয়েল্ড", "meaning": "বিনিয়োগ থেকে বছরে যা আয় হয়", "at_word": "w1"},
    "checklist": {"type": "checklist", "items": ["ভাড়া", "খরচ", "লাভ"], "title": "মনে রাখুন", "at_word": "w5"},
    "pros_cons": {"type": "pros_cons", "pros": ["সহজ", "দ্রুত"], "cons": ["ঝুঁকি আছে"], "at_word": "w4"},
    "stat_row": {"type": "stat_row", "stats": [{"value": "১০K", "label": "গ্রাহক"}, {"value": "৪.৮", "label": "রেটিং"}, {"value": "৯৯%", "label": "সময়মতো"}], "at_word": "w7"},
    "question": {"type": "question", "text": "কোনটা আসল লাভ?", "options": ["গ্রস", "নেট"], "answer": 1, "at_word": "w1"},
    "feature_grid": {"type": "feature_grid", "items": [{"title": "দ্রুত", "detail": "মিনিটেই তৈরি", "emoji": "26a1"}, {"title": "সহজ", "detail": "কোডিং ছাড়াই", "icon": "lucide:sparkles"}], "at_word": "w3"},
    "cta": {"type": "cta", "headline": "আজই শুরু করুন", "button": "ফ্রি ট্রাই", "sub": "কার্ড লাগবে না", "at_word": "w20"},
    "price_tag": {"type": "price_tag", "price": "৳৯৯৯", "old_price": "৳১৪৯৯", "label": "আজকের অফার", "at_word": "w15"},
    "device": {"type": "device", "kind": "phone", "media": None, "caption": "অ্যাপের হোম স্ক্রিন", "callouts": [{"text": "সহজ মেনু", "x": 0.5, "y": 0.3}], "at_word": "w4"},
    "speaker_card": {"type": "speaker_card", "name": "রিয়া", "text": "আমি মনে করি দাম কমানো উচিত", "side": "left", "color": 0, "at_word": "w2"},
    "story": {"type": "story", "bg": {"type": "room", "time": "evening"}, "tag": "Home", "at_word": "w3",
              "items": [{"type": "person", "char": "hero", "x": 160, "y": 560, "s": 0.8, "pose": "sit", "expr": "smile", "arm": "phone"},
                        {"type": "bubble", "text": "Yes!", "x": 230, "y": 220, "at": 1.2}]},
    "cartoon": {"type": "cartoon", "set": "market", "cast": [{"who": "boy", "pose": "walk", "expression": "happy", "x": 0.35}, {"who": "elder", "pose": "point", "x": 0.7, "flip": True}], "bubble": "এটার দাম কত?", "speaker": 0, "props": ["1f34e"], "at_word": "w3"},
    "media_frame": {"type": "media_frame", "media": "photo1", "frame": "polaroid", "caption": "আমাদের দোকান", "motion": "kenburns", "at_word": "w5"},
    "flow": {"type": "flow", "nodes": [{"text": "আয়", "kind": "start"}, {"text": "খরচ"}, {"text": "সঞ্চয়", "kind": "end"}], "at_word": "w2"},
    "cycle": {"type": "cycle", "items": ["উপার্জন", "খরচ", "সঞ্চয়", "বিনিয়োগ"], "center": "অর্থচক্র", "at_word": "w3"},
    "hierarchy": {"type": "hierarchy", "root": "বিনিয়োগ", "branches": [{"text": "ঝুঁকিহীন", "children": ["সঞ্চয়পত্র"]}, {"text": "ঝুঁকিপূর্ণ", "children": ["শেয়ার", "ক্রিপ্টো"]}], "at_word": "w2"},
    "venn": {"type": "venn", "sets": ["গ্রস", "নেট"], "overlap": "আয়", "at_word": "w4"},
    "funnel": {"type": "funnel", "stages": [{"label": "দর্শক", "value": "১০০০"}, {"label": "আগ্রহী", "value": "৩০০"}, {"label": "ক্রেতা", "value": "৫০"}], "at_word": "w2"},
    "pyramid": {"type": "pyramid", "levels": ["লক্ষ্য", "সঞ্চয়", "মৌলিক চাহিদা"], "at_word": "w3"},
    "matrix": {"type": "matrix", "x_label": "খরচ", "y_label": "লাভ", "quadrants": ["ভালো", "সেরা", "খারাপ", "ঝুঁকি"], "highlight": 1, "at_word": "w5"},
    "pictogram": {"type": "pictogram", "total": 10, "highlighted": 7, "emoji": "1f9d1", "label": "১০ জনের ৭ জন", "at_word": "w6"},
    "gauge": {"type": "gauge", "value": 72, "label": "ঝুঁকির মাত্রা", "low": "কম", "high": "বেশি", "at_word": "w4"},
}

USE_WHEN: dict[str, str] = {
    "shape": "A rectangle, circle, triangle or line to organize the scene or emphasize a spoken concept. Optional label must come from the script.",
    "title": "Name the topic or key term being explained. Usually first in a scene.",
    "value_card": "A price, amount or single number with context (label says what it is).",
    "big_number": "One striking statistic or percentage that deserves the whole screen.",
    "arrow": "Show cause -> effect, a flow, or a change between two elements.",
    "icon_row": "Repeated units: coins per year, people, years. count = how many.",
    "tag": "A short formula, rule of thumb or key phrase (e.g. '৪ = গ্রস').",
    "compare": "Two options with one number each (A vs B), optional verdict.",
    "list": "2-4 short points spoken one after another.",
    "equation": "Simple arithmetic idea built piece by piece.",
    "quote": "One statement the speaker stresses; keep it short.",
    "bar_chart": "2-5 numbers compared by height.",
    "icon": "One concept with no numbers: a single large icon plus label.",
    "keyword": "The ONE word the speaker stressed in the sentence, in huge animated type (with an optional icon/sticker). Use for emphasis scenes without numbers.",
    "sticker": "A big colour emoji for a concrete thing (a stone, a house, coins). Pops in and floats. Pair with a short label.",
    "ring": "A percentage or share (0-100): satisfaction, completion, market share. The ring fills up.",
    "line_chart": "3-8 numbers over time or steps: growth, decline, trend. The line draws itself.",
    "steps": "A process or how-to: 2-5 numbered steps, each a short title with an optional detail.",
    "timeline": "Dated events: years, days or phases in order.",
    "definition": "'X means Y' sentences: the term and its meaning on a card.",
    "checklist": "A recap or 2-5 requirements/benefits that tick off one by one.",
    "pros_cons": "Good vs bad, advantages vs drawbacks, before vs after (text only, no numbers).",
    "stat_row": "2-4 key figures side by side (customers, rating, uptime). Use for proof and results.",
    "question": "A question put to the viewer, optionally with choices and the correct answer.",
    "feature_grid": "2-4 product features or benefits, each with a small picture, a title and a line.",
    "cta": "The closing call to action: headline plus a button-like line.",
    "price_tag": "A price or offer, optionally with the old price crossed out.",
    "device": "Show the user's screenshot or video inside a phone, laptop or browser, with callouts. Needs a media id.",
    "speaker_card": "A named speaker's point in a discussion; the avatar moves while they talk.",
    "story": "Cartoon 2: a whole drawn scene from the story engine (a place, the shared cast, props, bubbles, numbers, effects), animated to the voice. Used by story videos (options.look = story); plan those with get_story_task / submit_story.",
    "cartoon": "Reusable animated story scenes: classic, ink or paper characters; 10 environments; still/push/pull/pan cameras; day/sunset/night lighting; image props and sign/chalk/paint/neon text. Use supplied facts and image.generate assets, then edit through the timeline. No new code per video.",
    "media_frame": "The user's own photo/GIF/clip as a framed picture. Needs a media id.",
    "flow": "A process or chain: 2-5 boxes joined by arrows (A leads to B leads to C).",
    "cycle": "Something that loops: 3-6 stages in a circle.",
    "hierarchy": "Types or parts of a whole: a root with 2-4 branches and leaves.",
    "venn": "What two (or three) things share and where they differ: overlapping circles.",
    "funnel": "Stages that narrow, optionally with numbers: conversion, filtering, drop-off.",
    "pyramid": "3-5 tiers from the top to the base: priorities, a hierarchy of needs.",
    "matrix": "A 2 x 2 grid with axis labels and four quadrants.",
    "pictogram": "A proportion said as 'x out of y' or '1 in 5': a grid of figures with some filled.",
    "gauge": "A dial from 0 to 100: a score, a risk level or a rating.",
}


@lru_cache(maxsize=1)
def icon_names() -> list[str]:
    return read_json(paths.ICONS / "curated.json", [])


@lru_cache(maxsize=1)
def all_icon_names() -> set[str]:
    from ..visuals.icons import all_names

    return set(all_names())


def component_catalogue() -> list[dict]:
    out = []
    for m in ELEMENT_MODELS:
        t = m.model_fields["type"].default
        schema = m.model_json_schema()
        props = {k: v for k, v in schema.get("properties", {}).items() if k not in ("id", "type")}
        out.append({
            "type": t,
            **library_info(t, EXAMPLES[t]),
            "description": inspect.getdoc(m) or "",
            "use_when": USE_WHEN.get(t, ""),
            "fields": props,
            "defs": schema.get("$defs", {}),
            "required": [r for r in schema.get("required", []) if r not in ("type",)],
            "example": library_info(t, EXAMPLES[t])["starter"],
        })
    return out


def catalogue_summary() -> dict:
    from ..visual_motion import catalogue as motion_catalogue
    from .visual_templates import templates
    elements=component_catalogue()
    return {
        "templates": templates(elements),
        "motion": motion_catalogue(),
        "elements": elements,
        "layouts": {
            "stack": "elements stacked vertically (9:16, 1:1) / main element left + rest right (16:9). Default.",
            "split": "elements split into two groups: top/bottom (9:16, 1:1) or left/right (16:9).",
            "hero": "first element enlarged; best with exactly 1-2 elements.",
            "grid": "elements in a two-column grid (cards, features).",
            "side": "wide screens: main visual left, text right; tall screens: stacked.",
            "lower": "elements sit in the lower part of the screen, over a photo or video backdrop.",
            "upper": "elements sit in the upper part of the screen (used when the people in the picture are low in the frame).",
        },
        "transitions": TRANSITIONS,
        "layout_names": LAYOUTS,
        "icons": icon_names(),
        "icon_note": "Any Lucide icon name is accepted; the list above is a curated starting set. 'coin' is a special round coin showing the theme currency.",
    }
