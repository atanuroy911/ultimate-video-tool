"""One scene per phase-2 element (infographics, cartoons, media, devices), rendered through HyperFrames: used by the render tests and as a
visual catalogue (`python -m vt.compose.showcase out_dir 9:16 paper`)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw

from .. import paths
from ..project import load_theme
from ..schema import Beat, Beats, ScenesFile, Transcript, Word
from ..util import read_json
from ..visuals import icons as icon_sets
from .composer import resolve_composition, write_composition


def make_photo(path: Path) -> None:
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:900, 0:1200]
    im = Image.fromarray(np.stack([(xx / 1200 * 255), (yy / 900 * 180 + 40), (255 - xx / 1200 * 200)], axis=-1).astype("uint8"))
    d = ImageDraw.Draw(im)
    for i in range(9):
        x0, y0 = int(rng.integers(0, 1000)), int(rng.integers(0, 700))
        d.ellipse((x0, y0, x0 + 200, y0 + 200), fill=tuple(int(v) for v in rng.integers(30, 255, 3)))
    im.save(path)


EL = {
    "title": {"type": "title", "text": "Hello"},
    "big": {"type": "big_number", "value": "4", "unit": "%", "label": "yield"},
    "ring": {"type": "ring", "value": 72, "label": "Happy customers", "display": "72%"},
    "line_chart": {"type": "line_chart", "points": [{"label": "2020", "value": 10}, {"label": "2021", "value": 14}, {"label": "2022", "value": 12}, {"label": "2023", "value": 25}, {"label": "2024", "value": 38}], "unit": "%", "label": "Growth"},
    "steps": {"type": "steps", "items": [{"title": "Paste script", "detail": "any language"}, {"title": "Pick a style", "detail": "or let it choose"}, {"title": "Generate", "detail": "get the video"}]},
    "timeline": {"type": "timeline", "events": [{"when": "2010", "what": "Started"}, {"when": "2015", "what": "First profit"}, {"when": "2024", "what": "Nationwide"}]},
    "definition": {"type": "definition", "term": "Inflation", "meaning": "Prices rise over time, so money buys less"},
    "checklist": {"type": "checklist", "items": ["Rent", "Food", "Fuel", "Savings"], "title": "Remember"},
    "pros_cons": {"type": "pros_cons", "pros": ["Easy to start", "Fast results"], "cons": ["Needs internet"], "pros_title": "Pros", "cons_title": "Cons"},
    "stat_row": {"type": "stat_row", "stats": [{"value": "10K", "label": "Customers"}, {"value": "4.8", "label": "Rating"}, {"value": "99%", "label": "On time"}]},
    "question": {"type": "question", "text": "Which one is the real profit?", "options": ["Gross", "Net", "Neither"], "answer": 1},
    "feature_grid": {"type": "feature_grid", "items": [{"title": "Fast", "detail": "Minutes, not hours", "emoji": "26a1"}, {"title": "Simple", "detail": "No skills needed", "icon": "lucide:sparkles"},
                     {"title": "Private", "detail": "Runs on your PC", "emoji": "1f512"}, {"title": "Free", "detail": "Open source", "emoji": "1f381"}]},
    "cta": {"type": "cta", "headline": "Start today", "button": "Try it free", "sub": "No card needed"},
    "price_tag": {"type": "price_tag", "price": "$19", "old_price": "$49", "label": "Launch offer"},
    "device": {"type": "device", "kind": "phone", "media": "photo", "caption": "The app", "callouts": [{"text": "Easy menu", "x": 0.35, "y": 0.3}, {"text": "Live preview", "x": 0.65, "y": 0.7}]},
    "device_laptop": {"type": "device", "kind": "laptop", "media": "photo", "caption": "Dashboard", "callouts": [{"text": "Reports", "x": 0.3, "y": 0.4}]},
    "device_browser": {"type": "device", "kind": "browser", "media": "photo", "caption": "", "callouts": []},
    "speaker_card": {"type": "speaker_card", "name": "Riya", "text": "I think schools should start later.", "side": "left", "color": 1},
    "speaker_right": {"type": "speaker_card", "name": "Sam", "text": "Parents would disagree.", "side": "right", "color": 3},
    "cartoon_market": {"type": "cartoon", "set": "market", "cast": [{"who": "boy", "pose": "walk", "expression": "happy", "x": 0.3}, {"who": "elder", "pose": "point", "x": 0.72, "flip": True}], "bubble": "How much is this?", "speaker": 0, "props": ["1f34e"]},
    "cartoon_office": {"type": "cartoon", "set": "office", "cast": [{"who": "woman", "pose": "think", "expression": "thinking", "x": 0.4}, {"who": "man", "pose": "wave", "expression": "happy", "x": 0.75, "flip": True}], "bubble": "", "props": []},
    "cartoon_village": {"type": "cartoon", "set": "village", "cast": [{"who": "man", "pose": "stand", "x": 0.25}, {"who": "boy", "pose": "sad", "expression": "sad", "x": 0.5}, {"who": "girl", "pose": "celebrate", "expression": "happy", "x": 0.78}], "bubble": "", "props": ["1f3e0"]},
    "cartoon_class": {"type": "cartoon", "set": "classroom", "cast": [{"who": "teacher", "pose": "point", "x": 0.35}, {"who": "robot", "pose": "shrug", "expression": "surprised", "x": 0.7, "flip": True}], "bubble": "Any questions?", "props": []},
    "cartoon_nature": {"type": "cartoon", "set": "nature", "cast": [{"who": "doctor", "pose": "celebrate", "expression": "happy", "x": 0.5}], "bubble": "", "props": []},
    "cartoon_street": {"type": "cartoon", "set": "street", "cast": [{"who": "worker", "pose": "shrug", "expression": "angry", "x": 0.5}], "bubble": "", "props": []},
    "cartoon_home": {"type": "cartoon", "set": "home", "cast": [{"who": "woman", "pose": "sit", "expression": "happy", "x": 0.4}], "bubble": "", "props": []},
    "cartoon_studio": {"type": "cartoon", "set": "studio", "cast": [{"who": "man", "pose": "stand", "expression": "neutral", "x": 0.5}], "bubble": "Welcome!", "props": []},
    "cartoon_shop": {"type": "cartoon", "set": "shop", "cast": [{"who": "elder", "pose": "wave", "expression": "happy", "x": 0.4}], "bubble": "", "props": []},
    "flow": {"type": "flow", "nodes": [{"text": "Idea", "kind": "start"}, {"text": "Script"}, {"text": "Review?", "kind": "decision"}, {"text": "Publish", "kind": "end"}]},
    "cycle": {"type": "cycle", "items": ["Earn", "Spend", "Save", "Invest"], "center": "Money loop"},
    "hierarchy": {"type": "hierarchy", "root": "Investing", "branches": [{"text": "Safe", "children": ["Savings", "Bonds"]}, {"text": "Risky", "children": ["Stocks", "Crypto", "Startups"]}]},
    "venn": {"type": "venn", "sets": ["Gross", "Net"], "overlap": "Income"},
    "venn3": {"type": "venn", "sets": ["Fast", "Cheap", "Good"], "overlap": "Dream"},
    "funnel": {"type": "funnel", "stages": [{"label": "Visitors", "value": "1,000"}, {"label": "Interested", "value": "300"}, {"label": "Buyers", "value": "50"}]},
    "pyramid": {"type": "pyramid", "levels": ["Goals", "Savings", "Basic needs"]},
    "matrix": {"type": "matrix", "x_label": "Cost", "y_label": "Profit", "quadrants": ["Good", "Best", "Bad", "Risky"], "highlight": 1},
    "pictogram": {"type": "pictogram", "total": 10, "highlighted": 7, "emoji": "1f9d1", "label": "7 out of 10 people"},
    "gauge": {"type": "gauge", "value": 72, "label": "Risk level", "low": "Low", "high": "High"},
    "media_polaroid": {"type": "media_frame", "media": "photo", "frame": "polaroid", "caption": "Our shop", "motion": "kenburns"},
    "media_tv": {"type": "media_frame", "media": "photo", "frame": "tv", "caption": "", "motion": "kenburns"},
}

NAMES = [n for n in EL if n not in ("title", "big")]
SCENE = 4.8


def build(out: Path, aspect: str, theme_name: str, names: Optional[list[str]] = None) -> tuple[Path, list[float]]:
    """Write the composition for the given elements; returns (index.html, a time inside each scene when its element is fully in)."""
    out.mkdir(parents=True, exist_ok=True)
    theme = load_theme(theme_name)
    photo = out / "photo.jpg"
    make_photo(photo)
    names = names or NAMES
    words, beats, scenes, t = [], [], [], 0.2
    for i, n in enumerate(names):
        ids = []
        for k in range(5):
            w = Word(id=f"w{len(words) + 1}", text=f"word{k}", start=round(t, 2), end=round(t + 0.8, 2))
            words.append(w)
            ids.append(w.id)
            t += 0.9
        beats.append(Beat(id=f"b{i + 1}", word_ids=ids, start=words[-5].start, end=words[-1].end, text="x"))
        el = dict(EL[n])
        el["at_word"] = ids[0]
        scenes.append({"id": f"s{i + 1}", "beats": [f"b{i + 1}"], "transition_in": "cut" if i == 0 else "fade", "elements": [el]})
        t += 0.3
    dur = round(t + 0.3, 2)
    sf = ScenesFile.model_validate({"theme": theme.name, "planner": "manual", "scenes": scenes})
    envelope = {"dt": 0.04, "v": [round(0.5 + 0.5 * float(np.sin(i / 2.5)), 2) for i in range(int(dur / 0.04))]}
    media = {"photo": {"src": "media/photo.jpg", "kind": "image", "fx": 0.5, "fy": 0.5, "w": 1200, "h": 900, "trim": 0, "loop": False, "_abs": str(photo)}}
    data = resolve_composition(sf, Transcript(words=words), Beats(beats=beats), theme, aspect, dur, None, media=media, envelope=envelope, language="en")
    icons = read_json(paths.ICONS / "lucide.json", {})
    data["icons"] = {k: (icons.get(k) or icon_sets.inner(k) or "") for k in ["lucide:sparkles", "circle-help"]}
    return write_composition(out / "comp", data, theme), [round(s["start"] + 3.4, 2) for s in data["scenes"]]


def render(out: Path, aspect: str = "9:16", theme_name: str = "paper", names: Optional[list[str]] = None) -> list[Path]:
    from ..render.hyperframes import snapshot

    idx, times = build(out, aspect, theme_name, names)
    return snapshot(idx.parent, out / "snap", times)


def contact_sheet(frames: list[Path], aspect: str, dest: Path, cols: Optional[int] = None) -> Path:
    w, h = {"9:16": (270, 480), "1:1": (360, 360), "16:9": (480, 270)}[aspect]
    cols = cols or {"9:16": 6, "1:1": 5, "16:9": 4}[aspect]
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    for i, f in enumerate(frames):
        sheet.paste(Image.open(f).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(dest)
    return dest


if __name__ == "__main__":
    out, asp, th = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    fr = render(out, asp, th, sys.argv[4:] or None)
    print(contact_sheet(fr, asp, out / f"sheet-{asp.replace(':', 'x')}.png"))
