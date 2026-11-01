"""Builds projects/<id> from a hand-written Banglish script with synthetic word timings and a silent wav.
Used as a fixture to test composer/render/mux without ASR. Usage: python samples/build_reference.py [project-id]"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vt import paths  # noqa: E402
from vt.project import Project  # noqa: E402
from vt.schema import Beat, Beats, Cuts, ProjectMeta, ScenesFile, Transcript, Word  # noqa: E402
from vt.stages.words import build_beats  # noqa: E402
from vt.util import now_iso, write_json  # noqa: E402

SENTENCES = [
    "ইয়েল্ড মানে কী?",
    "ধরুন দোকানের দাম একশো টাকা।",
    "বছরে ভাড়া পাচ্ছেন তিন টাকা।",
    "এটাকে বলে গ্রস ইয়েল্ড চার শতাংশ।",
    "কিন্তু খরচ বাদ দিয়া পকেটে যেটা থাকবে,",
    "সেটাই আসল net yield।",
]


def is_en(t: str) -> bool:
    return t.isascii() and any(c.isalpha() for c in t)


def main(pid: str = "reference") -> None:
    words: list[Word] = []
    t = 0.35
    n = 0
    for sent in SENTENCES:
        for tok in sent.split():
            n += 1
            dur = 0.28 + 0.035 * len(tok)
            words.append(Word(id=f"w{n}", text=tok, start=round(t, 3), end=round(t + dur, 3), lang="en" if is_en(tok) else "bn"))
            t += dur + 0.06
        t += 0.3
    duration = round(t + 0.4, 3)
    # sentences are derived exactly as the real pipeline does, so word edits keep the plan valid
    beats = build_beats(Transcript(language="bn", words=words)).beats
    assert [b.id for b in beats] == ["b1", "b2", "b3", "b4", "b5"], [b.text for b in beats]

    wid = {w.text: w.id for w in words}
    by_text = lambda s: next(w.id for w in words if w.text == s)  # noqa: E731

    scenes = ScenesFile.model_validate({
        "theme": "paper",
        "planner": "manual",
        "scenes": [
            {"id": "s1", "beats": ["b1"], "layout": "stack", "transition_in": "cut",
             "elements": [{"type": "title", "text": "ইয়েল্ড", "at_word": "w1"},
                          {"type": "icon", "name": "circle-help", "label": "কী এটা?", "at_word": "w3"}]},
            {"id": "s2", "beats": ["b2", "b3", "b4"], "layout": "stack", "transition_in": "slide_up",
             "elements": [
                 {"type": "title", "text": "ইয়েল্ড", "at_word": by_text("ধরুন")},
                 {"type": "value_card", "value": "৳১০০", "label": "দোকানের দাম", "at_word": by_text("একশো")},
                 {"type": "arrow", "direction": "down", "at_word": by_text("বছরে")},
                 {"type": "icon_row", "icon": "coin", "count": 3, "label": "বছরে ভাড়া", "at_word": by_text("তিন")},
                 {"type": "tag", "text": "৪ = গ্রস", "at_word": by_text("এটাকে")}],
             "caption": {"highlight_words": [by_text("একশো")]}},
            {"id": "s3", "beats": ["b5"], "layout": "stack", "transition_in": "zoom",
             "elements": [{"type": "compare", "left": {"title": "গ্রস", "value": "৪%"}, "right": {"title": "নেট", "value": "৩%"},
                           "verdict": "আসল লাভ নেট", "at_word": by_text("সেটাই")}],
             "caption": {"highlight_words": [by_text("থাকবে,"), by_text("net")]}},
        ],
    })

    proj = Project(pid)
    if proj.dir.exists():  # start from a clean slate so edits/undo files from earlier sessions cannot leak in
        shutil.rmtree(proj.dir)
    proj.dir.mkdir(parents=True, exist_ok=True)
    wav = proj.dir / "input.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=mono", "-t", str(duration), str(wav)], check=True)
    for name in ("audio.master.wav", "audio.cut.wav"):  # the cut stage would write these; the fixture's audio is silent anyway
        shutil.copyfile(wav, proj.dir / name)
    proj.save_meta(ProjectMeta(id=pid, title="Reference frame", created_at=now_iso(), status="planned"))
    proj.save_transcript(Transcript(language="bn", words=words))
    # a raw (source-time) transcript, as the ASR stage would write it, so word edits can rebuild transcript.json
    write_json(proj.raw_transcript_path, {"language": "bn", "model": "fixture", "duration": duration,
                                          "words": [{"text": w.text, "start": w.start, "end": w.end, "conf": 0.95} for w in words]})
    write_json(proj.beats_path, Beats(beats=beats).model_dump())
    write_json(proj.cuts_path, Cuts(source_duration=duration, keep=[(0.0, duration)]).model_dump())
    proj.save_scenes(scenes)
    print("built", proj.dir, "duration", duration, "words", len(words))


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []))
