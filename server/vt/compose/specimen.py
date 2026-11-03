"""A built-in sample video that shows every component. Used by the Studio theme editor for live preview."""
from __future__ import annotations

from pathlib import Path

from .. import paths
from ..schema import Beat, Beats, ScenesFile, Theme, Transcript, Word
from ..util import read_json
from .composer import FORMATS, resolve_composition, write_composition

SENTENCES = [
    "ইয়েল্ড মানে কী?",
    "দোকানের দাম একশো টাকা, বছরে ভাড়া তিন টাকা।",
    "গ্রস চার শতাংশ বনাম নেট তিন শতাংশ।",
    "বছরে চার শতাংশ আয়।",
    "ভাড়া, খরচ আর net লাভ।",
    "আয় বিয়োগ খরচ সমান লাভ।",
    "যেটা পকেটে থাকে সেটাই আসল।",
]


def build_specimen() -> tuple[Transcript, Beats, ScenesFile, float]:
    words: list[Word] = []
    beats: list[Beat] = []
    t, n = 0.3, 0
    for bi, sent in enumerate(SENTENCES, 1):
        ids, start = [], t
        for tok in sent.split():
            n += 1
            dur = 0.3 + 0.03 * len(tok)
            words.append(Word(id=f"w{n}", text=tok, start=round(t, 3), end=round(t + dur, 3), lang="en" if tok.isascii() else "bn"))
            ids.append(f"w{n}")
            t += dur + 0.06
        beats.append(Beat(id=f"b{bi}", word_ids=ids, start=round(start, 3), end=round(t - 0.06, 3), text=sent))
        t += 0.8
    duration = round(t + 0.3, 3)

    def w(text: str) -> str:
        return next(x.id for x in words if x.text == text)

    scenes = ScenesFile.model_validate({"theme": "paper", "planner": "manual", "scenes": [
        {"id": "s1", "beats": ["b1"], "transition_in": "cut", "elements": [
            {"type": "title", "text": "ইয়েল্ড", "at_word": w("ইয়েল্ড")}, {"type": "icon", "name": "circle-help", "label": "কী এটা?", "at_word": w("কী?")}]},
        {"id": "s2", "beats": ["b2"], "transition_in": "slide_up", "elements": [
            {"type": "value_card", "value": "৳১০০", "label": "দোকানের দাম", "at_word": w("একশো")},
            {"type": "arrow", "direction": "down", "at_word": w("বছরে")},
            {"type": "icon_row", "icon": "coin", "count": 3, "label": "বছরে ভাড়া", "at_word": w("তিন")}],
         "caption": {"highlight_words": [w("ভাড়া,")]}},
        {"id": "s3", "beats": ["b3"], "transition_in": "zoom", "elements": [
            {"type": "compare", "left": {"title": "গ্রস", "value": "৪%"}, "right": {"title": "নেট", "value": "৩%"}, "verdict": "আসল লাভ নেট", "at_word": w("গ্রস")}]},
        {"id": "s4", "beats": ["b4"], "transition_in": "slide_left", "elements": [
            {"type": "big_number", "value": "৪", "unit": "%", "label": "বছরে আয়", "at_word": w("চার")}]},
        {"id": "s5", "beats": ["b5"], "transition_in": "wipe", "elements": [
            {"type": "list", "items": ["ভাড়া", "খরচ", "net লাভ"], "at_word": w("ভাড়া,")}],
         "caption": {"highlight_words": [w("net")]}},
        {"id": "s6", "beats": ["b6"], "transition_in": "fade", "elements": [
            {"type": "equation", "parts": [{"text": "আয়"}, {"text": "−"}, {"text": "খরচ"}, {"text": "="}, {"text": "লাভ", "kind": "res"}], "at_word": w("আয়")},
            {"type": "tag", "text": "৪ = গ্রস", "at_word": w("সমান")}]},
        {"id": "s7", "beats": ["b7"], "transition_in": "whip", "elements": [
            {"type": "bar_chart", "bars": [{"label": "গ্রস", "value": 4, "display": "৪%"}, {"label": "নেট", "value": 3, "display": "৩%"}, {"label": "ঝুঁকি", "value": 1.5, "display": "১.৫%"}], "at_word": w("যেটা")},
            {"type": "quote", "text": "যেটা পকেটে থাকে সেটাই আসল", "at_word": w("সেটাই")}]},
    ]})
    return Transcript(language="bn", words=words), Beats(beats=beats), scenes, duration


def specimen_data(theme: Theme, aspect: str) -> dict:
    tr, beats, scenes, duration = build_specimen()
    icons = read_json(paths.ICONS / "lucide.json", {})
    return resolve_composition(scenes, tr, beats, theme, aspect, duration, icons)


def write_specimen(theme: Theme, aspect: str, root: Path | None = None) -> Path:
    root = root or (paths.PROJECTS / ".specimen")
    out = root / FORMATS[aspect]["tag"]
    return write_composition(out, specimen_data(theme, aspect), theme, "Specimen", all_fonts=True)
