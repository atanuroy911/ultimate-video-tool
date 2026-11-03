"""Human labels and editable starter content for the shared component catalogue."""

GROUPS = {
    "Text": "title keyword tag quote definition question cta",
    "Numbers & charts": "value_card big_number bar_chart ring line_chart stat_row price_tag pictogram gauge",
    "Lists & diagrams": "list equation steps timeline checklist pros_cons compare feature_grid flow cycle hierarchy venn funnel pyramid matrix",
    "Pictures & characters": "icon icon_row sticker device speaker_card cartoon media_frame",
    "Shapes": "shape arrow",
}
NAMES = {"cta": "Call to action", "pros_cons": "Pros and cons", "stat_row": "Key numbers", "media_frame": "Framed picture",
         "ring": "Progress ring", "icon_row": "Repeated icons", "big_number": "Large number", "value_card": "Number card",
         "pictogram": "People chart", "device": "Device frame", "speaker_card": "Speaker card", "shape": "Simple shape"}

# These are starters, not claims. The library explicitly asks users to replace sample content.
STARTERS = {
    "title": {"text": "Your title"}, "value_card": {"value": "0", "label": "Your label"},
    "big_number": {"value": "0", "unit": "%", "label": "Your label"}, "arrow": {"label": ""},
    "icon_row": {"icon": "star", "count": 3, "label": "Your label"}, "tag": {"text": "Key idea"},
    "compare": {"left": {"title": "Option A", "value": "0"}, "right": {"title": "Option B", "value": "0"}, "verdict": ""},
    "list": {"items": ["First point", "Second point"]},
    "equation": {"parts": [{"text": "A"}, {"text": "+"}, {"text": "B"}, {"text": "="}, {"text": "C", "kind": "res"}]},
    "quote": {"text": "Your quotation", "by": ""},
    "bar_chart": {"bars": [{"label": "A", "value": 1, "display": "1"}, {"label": "B", "value": 2, "display": "2"}]},
    "icon": {"name": "star", "label": "Your idea"}, "keyword": {"text": "Key idea"}, "sticker": {"label": ""},
    "ring": {"value": 0, "label": "Your progress"},
    "line_chart": {"points": [{"label": "A", "value": 0}, {"label": "B", "value": 1}, {"label": "C", "value": 2}], "unit": "", "label": "Your data"},
    "steps": {"items": [{"title": "First step", "detail": ""}, {"title": "Next step", "detail": ""}]},
    "timeline": {"events": [{"when": "Start", "what": "First event"}, {"when": "Next", "what": "Next event"}]},
    "definition": {"term": "Your term", "meaning": "What it means"},
    "checklist": {"items": ["First item", "Next item"], "title": "Your checklist"},
    "pros_cons": {"pros": ["An advantage"], "cons": ["A drawback"]},
    "stat_row": {"stats": [{"value": "0", "label": "First measure"}, {"value": "0", "label": "Next measure"}]},
    "question": {"text": "Your question?", "options": [], "answer": None},
    "feature_grid": {"items": [{"title": "First feature", "detail": "Your description", "emoji": "26a1"}, {"title": "Next feature", "detail": "Your description", "icon": "star"}]},
    "cta": {"headline": "Your next step", "button": "Learn more", "sub": ""},
    "price_tag": {"price": "0", "old_price": "", "label": "Your price"},
    "device": {"caption": "Your screenshot", "callouts": []},
    "speaker_card": {"name": "Speaker", "text": "Your spoken line"},
    "cartoon": {"bubble": "Your dialogue"},
    "media_frame": {"caption": "Your picture"},
    "flow": {"nodes": [{"text": "Start", "kind": "start"}, {"text": "Next step"}, {"text": "Finish", "kind": "end"}]},
    "cycle": {"items": ["Start", "Next", "Repeat"], "center": "Your cycle"},
    "hierarchy": {"root": "Main idea", "branches": [{"text": "Group A", "children": ["Item A"]}, {"text": "Group B", "children": ["Item B"]}]},
    "venn": {"sets": ["Group A", "Group B"], "overlap": "Shared"},
    "funnel": {"stages": [{"label": "First", "value": ""}, {"label": "Next", "value": ""}, {"label": "Last", "value": ""}]},
    "pyramid": {"levels": ["Top", "Middle", "Base"]},
    "matrix": {"x_label": "Horizontal", "y_label": "Vertical", "quadrants": ["A", "B", "C", "D"]},
    "pictogram": {"label": "Your proportion"}, "gauge": {"value": 0, "label": "Your measure", "low": "Low", "high": "High"},
}


def library_info(kind: str, example: dict) -> dict:
    return {
        "name": NAMES.get(kind, kind.replace("_", " ").capitalize()),
        "category": next((group for group, kinds in GROUPS.items() if kind in kinds.split()), "More"),
        "starter": {**example, **STARTERS.get(kind, {})},
    }
