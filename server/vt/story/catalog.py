"""Cartoon 2 (story engine): every item type, background and property, described once.

The same description validates plans (vt/schema.py Story), tells any AI director what exists (vt/story/designer.py) and builds the Studio's property
forms (GET /api/story/catalog -> client StoryEditor), so a property the renderer draws (server/renderer/story/src) can always be edited.
A property is {"k": kind, ...}: num (min, max, step), text, bool, color, enum (options), char (a cast id), time (one video second), times (several),
list (of text), numbers, schedule (timed changes [{t, <key>}]), keyframes, lines (phone screen lines), media, json (free structure).
Times are absolute video seconds, like the engine's: they follow the spoken words, which do not move when a scene is retimed.
"""
from __future__ import annotations

from typing import Any

ENTER = ["none", "pop", "fade", "slideL", "slideR", "slideUp", "slideDown", "drop", "stamp", "grow"]
EXIT = ["none", "fade", "pop"]
LOOP = ["none", "breathe", "bob", "walk", "float", "shake", "pulse", "spin", "sway", "glow"]
EXPR = ["neutral", "smile", "sad", "scared", "shock", "cry", "angry", "sleep"]
ARM = ["rest", "lap", "phone", "phoneEar", "raise", "wave", "point", "reach", "knock", "hug", "headPat", "face", "desk", "hold"]
ICONS = ["check", "cross", "x", "question", "exclaim", "star", "bulb", "heart", "lock", "bell", "money", "book", "home", "warning", "fire", "zzz",
         "trophy", "mail", "music", "server"]
TIMES_OF_DAY = ["day", "morning", "evening", "night", "dark"]
FONTS = ["serif", "hind", "sans", "latin"]


def num(lo: float, hi: float, step: float = 1, **kw) -> dict:
    return {"k": "num", "min": lo, "max": hi, "step": step, **kw}


def enum(options: list[str], **kw) -> dict:
    return {"k": "enum", "options": options, **kw}


def kind(k: str, **kw) -> dict:
    return {"k": k, **kw}


TEXT, BOOL, COLOR, CHAR, JSON = kind("text"), kind("bool"), kind("color"), kind("char"), kind("json")
SECOND = kind("time")

# every item: place, size, order and animation
COMMON: dict[str, dict] = {
    "x": num(-600, 1200, 1, label="Left to right"), "y": num(-200, 1200, 1, label="Top to bottom"),
    "s": num(0.05, 6, 0.05, label="Size", default=1), "rot": num(-360, 360, 1, label="Turn", default=0),
    "opacity": num(0, 1, 0.05, label="Opacity", default=1), "z": num(-20, 80, 1, label="Draw order"),
    "flip": kind("bool", label="Face the other way"),
    "at": kind("time", label="Appears at"), "until": kind("time", label="Leaves at"),
    "enter": enum(ENTER, label="Comes in by"), "exit": enum(EXIT, label="Leaves by"),
    "loop": enum(LOOP, label="Keeps moving"), "loopAmp": num(0, 4, 0.1, label="Movement strength", default=1),
    "move": kind("keyframes", label="Movement points"),
}

ELEMENTS: dict[str, dict[str, Any]] = {
    # people
    "person": {"group": "People", "label": "Character", "props": {
        "char": kind("char", label="Who"), "pose": enum(["sit", "stand"], label="Pose"), "expr": enum(EXPR, label="Face"),
        "arm": enum(ARM, label="Arm"), "exprs": kind("schedule", key="expr", options=EXPR, label="Face changes"),
        "arms": kind("schedule", key="arm", options=ARM, label="Arm changes"),
        "talk": kind("bool", label="Mouth always moving")}},
    "mini": {"group": "People", "label": "Small figure", "props": {"char": kind("char", label="Who"), "color": COLOR, "skin": COLOR}},
    "crowd": {"group": "People", "label": "Crowd", "props": {"count": num(1, 12, 1, label="People"), "texts": kind("list", label="Bubbles"),
              "laugh": kind("bool", label="Laughing"), "dark": BOOL, "gap": num(30, 200, 1, label="Spacing")}},
    # speech
    "bubble": {"group": "Speech", "label": "Speech bubble", "props": {"text": TEXT, "tail": enum(["l", "r", "none"], label="Tail"), "dark": BOOL,
               "w": num(40, 500, 1, label="Width"), "size": num(10, 60, 1, label="Text size")}},
    "thought": {"group": "Speech", "label": "Thought cloud", "props": {"text": TEXT, "icon": enum([""] + ICONS, label="Icon"), "w": num(80, 500, 1),
                "h": num(60, 400, 1), "size": num(10, 60, 1), "tailX": num(-300, 300, 1, label="Tail position"), "iconScale": num(0.2, 3, 0.1)}},
    # text and cards
    "title": {"group": "Text", "label": "Title", "props": {"text": TEXT, "size": num(12, 160, 1), "color": COLOR, "hl": kind("color", label="Highlight"),
              "font": enum(FONTS), "anchor": enum(["start", "middle", "end"]), "typewriter": BOOL, "cps": num(1, 60, 1, label="Letters per second")}},
    "text": {"group": "Text", "label": "Text", "props": {"text": TEXT, "size": num(12, 160, 1), "color": COLOR, "hl": kind("color", label="Highlight"),
             "font": enum(FONTS), "anchor": enum(["start", "middle", "end"]), "typewriter": BOOL, "cps": num(1, 60, 1, label="Letters per second")}},
    "pill": {"group": "Text", "label": "Label pill", "props": {"text": TEXT, "fill": COLOR, "color": COLOR, "size": num(10, 80, 1), "w": num(40, 520, 1),
             "font": enum(FONTS)}},
    "card": {"group": "Text", "label": "Card", "props": {"title": TEXT, "text": TEXT, "w": num(60, 520, 1), "h": num(40, 800, 1), "lines": num(0, 12, 1),
             "fill": COLOR, "titleFill": COLOR, "color": COLOR, "size": num(10, 80, 1), "r": num(0, 60, 1, label="Corner")}},
    "quote": {"group": "Text", "label": "Quote", "props": {"text": TEXT, "w": num(100, 520, 1), "h": num(60, 600, 1), "fill": COLOR, "size": num(10, 80, 1)}},
    "badge": {"group": "Text", "label": "Badge", "props": {"text": TEXT, "sub": TEXT, "fill": COLOR, "color": COLOR, "r": num(20, 200, 1),
              "size": num(10, 100, 1)}},
    "stamp": {"group": "Text", "label": "Stamp", "props": {"text": TEXT, "color": COLOR, "fill": COLOR, "shape": enum(["rect", "circle"]),
              "font": enum(FONTS), "size": num(10, 90, 1), "w": num(40, 520, 1)}},
    "steps": {"group": "Text", "label": "Steps", "props": {"items": kind("list", label="Steps"), "times": kind("times", label="Each appears at"),
              "gap": num(60, 300, 1), "size": num(10, 70, 1), "numFill": COLOR}},
    "paper": {"group": "Text", "label": "Paper sheet", "props": {"title": TEXT, "sub": TEXT, "footer": TEXT, "lines": num(0, 12, 1), "fill": COLOR}},
    "note": {"group": "Text", "label": "Small note", "props": {"fill": COLOR}},
    # numbers
    "counter": {"group": "Numbers", "label": "Counting number", "props": {"from": num(-1e9, 1e9, 1), "to": num(-1e9, 1e9, 1),
                "decimals": num(0, 4, 1), "prefix": TEXT, "suffix": TEXT, "dur": num(0.1, 20, 0.1, label="Counting time"), "size": num(10, 200, 1),
                "color": COLOR, "latin": kind("bool", label="Latin digits")}},
    "gauge": {"group": "Numbers", "label": "Gauge", "props": {"label": TEXT, "value": num(0, 1, 0.01), "from": num(0, 1, 0.01), "to": num(0, 1, 0.01),
              "dur": num(0.1, 20, 0.1), "h": num(60, 700, 1), "color": COLOR, "labelColor": COLOR}},
    "progress": {"group": "Numbers", "label": "Progress bar", "props": {"label": TEXT, "value": num(0, 1, 0.01), "from": num(0, 1, 0.01),
                 "to": num(0, 1, 0.01), "dur": num(0.1, 20, 0.1), "w": num(80, 520, 1), "color": COLOR}},
    "bars": {"group": "Numbers", "label": "Bar chart", "props": {"values": kind("numbers", label="Values"), "labels": kind("list", label="Labels"),
             "max": num(0, 1e9, 1), "h": num(40, 600, 1), "bw": num(10, 200, 1, label="Bar width"), "gap": num(0, 200, 1)}},
    "calendar": {"group": "Numbers", "label": "Calendar days", "props": {"count": num(1, 31, 1), "start": num(1, 31, 1), "interval": num(0.05, 3, 0.05),
                 "label": TEXT, "cols": num(1, 10, 1), "color": COLOR, "labelColor": COLOR}},
    "clock": {"group": "Numbers", "label": "Clock", "props": {"hour": num(0, 23, 1), "minute": num(0, 59, 1), "r": num(30, 300, 1),
              "spin": num(-20, 20, 0.5)}},
    "heart": {"group": "Numbers", "label": "Heart", "props": {"beats": kind("times", label="Beats at"), "color": COLOR, "broken": BOOL}},
    "eyes": {"group": "Numbers", "label": "Watching eyes", "props": {"points": JSON, "look": JSON}},
    "icon": {"group": "Numbers", "label": "Icon", "props": {"name": enum(ICONS, label="Icon")}},
    # things
    "phone": {"group": "Things", "label": "Phone", "props": {"header": TEXT, "headerFill": COLOR, "lines": kind("lines", label="Screen lines"),
              "typing": JSON, "big": kind("text", label="Big text"), "bigAt": kind("time", label="Big text at"), "bigSize": num(10, 160, 1),
              "bigColor": COLOR, "loading": kind("times", label="Loading from / to"), "icon": enum([""] + ICONS), "iconAt": kind("time", label="Icon at"),
              "dark": BOOL, "hands": BOOL, "glow": BOOL, "skin": COLOR}},
    "monitor": {"group": "Things", "label": "Monitor", "props": {"text": TEXT, "screen": COLOR, "color": COLOR, "size": num(10, 60, 1)}},
    "door": {"group": "Things", "label": "Door", "props": {"open": num(0, 1, 0.05), "closeAt": kind("time", label="Closes at"),
             "openAt": kind("time", label="Opens at"), "color": COLOR}},
    "window": {"group": "Things", "label": "Window", "props": {"time": enum(TIMES_OF_DAY), "sky": COLOR}},
    "bed": {"group": "Things", "label": "Bed", "props": {"w": num(80, 520, 1), "color": COLOR}},
    "sofa": {"group": "Things", "label": "Sofa", "props": {"w": num(80, 520, 1), "color": COLOR}},
    "desk": {"group": "Things", "label": "Desk", "props": {"w": num(80, 520, 1)}},
    "chair": {"group": "Things", "label": "Chair", "props": {}},
    "lamp": {"group": "Things", "label": "Lamp", "props": {}},
    "books": {"group": "Things", "label": "Books", "props": {}},
    "cup": {"group": "Things", "label": "Cup", "props": {"color": COLOR, "steam": BOOL}},
    "bag": {"group": "Things", "label": "Bag", "props": {}},
    "plant": {"group": "Things", "label": "Plant", "props": {}},
    "tree": {"group": "Things", "label": "Tree", "props": {"color": COLOR}},
    "house": {"group": "Things", "label": "House", "props": {"color": COLOR, "lit": kind("bool", label="Lights on")}},
    "car": {"group": "Things", "label": "Car", "props": {"color": COLOR, "wheelSpin": num(-30, 30, 0.5, label="Wheel speed")}},
    # effects
    "particles": {"group": "Effects", "label": "Particles", "props": {"kind": enum(["stars", "rain", "snow", "hearts", "confetti", "sparkle"]),
                  "count": num(1, 120, 1), "color": COLOR}},
    "overlay": {"group": "Effects", "label": "Colour wash", "props": {"color": COLOR, "alpha": num(0, 1, 0.05, label="Strength")}},
    "ecg": {"group": "Effects", "label": "Heartbeat line", "props": {"color": COLOR}},
    "arrow": {"group": "Effects", "label": "Arrow", "props": {"dx": num(-600, 600, 1), "dy": num(-600, 600, 1), "curve": num(-300, 300, 1), "color": COLOR,
              "w": num(1, 30, 1)}},
    "lines": {"group": "Effects", "label": "Impact lines", "props": {"color": COLOR}},
    "spotlight": {"group": "Effects", "label": "Spotlight", "props": {"r": num(40, 800, 1), "color": COLOR}},
    "shape": {"group": "Effects", "label": "Shape", "props": {"shape": enum(["rect", "circle", "ellipse", "line", "path"]), "w": num(1, 1000, 1),
              "h": num(1, 1000, 1), "r": num(1, 500, 1), "rx": num(0, 500, 1), "ry": num(0, 500, 1), "dx": num(-1000, 1000, 1),
              "dy": num(-1000, 1000, 1), "d": TEXT, "fill": COLOR, "stroke": COLOR, "strokeWidth": num(0, 40, 0.5)}},
    "image": {"group": "Effects", "label": "Picture", "props": {"src": kind("media", label="Picture"), "w": num(10, 1000, 1), "h": num(10, 1000, 1)}},
    "group": {"group": "Effects", "label": "Group", "props": {"children": JSON}},
}

BACKGROUNDS: dict[str, dict[str, Any]] = {
    "plain": {"label": "Plain colour", "props": {"color": COLOR}},
    "gradient": {"label": "Gradient", "props": {"from": COLOR, "to": COLOR}},
    "room": {"label": "Room", "props": {"time": enum(TIMES_OF_DAY), "window": BOOL, "windowX": num(-200, 700, 1), "wall": COLOR, "floor": COLOR,
             "frame": kind("bool", label="Picture frame"), "frameX": num(-200, 700, 1), "lamp": BOOL, "lampX": num(-200, 700, 1)}},
    "living": {"label": "Living room", "props": {"time": enum(TIMES_OF_DAY), "wall": COLOR, "floor": COLOR}},
    "split": {"label": "Two rooms", "props": {"left": COLOR, "right": COLOR, "splitX": num(40, 500, 1)}},
    "street": {"label": "Street", "props": {"time": enum(TIMES_OF_DAY)}},
    "exterior": {"label": "House front", "props": {"time": enum(TIMES_OF_DAY), "wall": COLOR, "roof": COLOR}},
    "office": {"label": "Office", "props": {"time": enum(TIMES_OF_DAY)}},
    "classroom": {"label": "Classroom", "props": {"board": kind("text", label="Board text")}},
    "shop": {"label": "Tea stall", "props": {}},
    "park": {"label": "Park", "props": {"time": enum(TIMES_OF_DAY)}},
    "nightsky": {"label": "Night sky", "props": {}},
}
BG_COMMON: dict[str, dict] = {"dark": num(0, 1, 0.05, label="Darken"), "tint": kind("color", label="Tint"), "tintOpacity": num(0, 1, 0.05, label="Tint strength"),
                              "glow": kind("color", label="Warm glow"), "darkAt": kind("time", label="Darken from"),
                              "darkEnd": kind("time", label="Darken until"), "darkFrom": num(0, 1, 0.05), "darkTo": num(0, 1, 0.05)}

CHARACTER: dict[str, dict] = {"name": TEXT, "skin": kind("color", label="Skin"), "ear": kind("color", label="Ear"), "shirt": kind("color", label="Top"),
                              "pants": kind("color", label="Trousers"), "hair": kind("color", label="Hair"), "bun": kind("bool", label="Hair bun"),
                              "orna": kind("color", label="Scarf"), "lungi": kind("color", label="Long skirt or sari"),
                              "glasses": kind("bool", label="Glasses"), "mustache": kind("color", label="Moustache"), "long": kind("bool", label="Long top")}

SFX = {"tick": "click", "pop": "pop", "stamp": "impact", "whoosh": "whoosh", "printer": "typing"}      # engine sound -> our library role (vt/sfxlib.py)


def time_paths(item: dict) -> list[tuple]:
    """Where an item keeps video seconds (so a whole story can be shifted when the speech is cut again)."""
    out: list[tuple] = [(k,) for k, spec in {**COMMON, **ELEMENTS.get(item.get("type"), {}).get("props", {})}.items() if spec["k"] == "time" and k in item]
    for k, spec in {**COMMON, **ELEMENTS.get(item.get("type"), {}).get("props", {})}.items():
        if spec["k"] == "times" and isinstance(item.get(k), list):
            out += [(k, i) for i in range(len(item[k]))]
        if spec["k"] in ("schedule", "keyframes", "lines") and isinstance(item.get(k), list):
            out += [(k, i, "t" if spec["k"] != "lines" else "at") for i in range(len(item[k]))]
    if isinstance(item.get("typing"), dict) and "at" in item["typing"]:
        out.append(("typing", "at"))
    return out


def listing() -> dict:
    """The catalog for the Studio and for directors."""
    return {"elements": ELEMENTS, "common": COMMON, "backgrounds": BACKGROUNDS, "background_common": BG_COMMON, "character": CHARACTER,
            "enter": ENTER, "exit": EXIT, "loop": LOOP, "expressions": EXPR, "arms": ARM, "icons": ICONS}
