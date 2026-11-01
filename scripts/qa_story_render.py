"""Renders what the story director (vt/script/story.py) makes from the evaluation transcripts and writes a contact sheet per transcript (one frame per second) to look at.

    python scripts/qa_story_render.py [--sets story-wallet,story-fox] [--aspect 16:9] [--out qa_out_story]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "script_eval"))
from transcripts import SETS  # noqa: E402

from vt.compose.composer import resolve_composition, write_composition  # noqa: E402
from vt.planner import plan_rules  # noqa: E402
from vt.project import load_theme  # noqa: E402
from vt.render.hyperframes import snapshot  # noqa: E402
from vt.script import compile_script, examples as EX  # noqa: E402
from vt.script.story import story_script  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="story-wallet,story-fox,edu-money,discussion-remote")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--out", default=str(ROOT / "qa_out_story"))
    a = ap.parse_args()
    theme = load_theme("paper")
    for name in a.sets.split(","):
        tr, beats = EX.make(SETS[name])
        sf = plan_rules(tr, beats, "paper", language="en")
        script = story_script(tr, beats, sf, kind="stick", language="en", aspect=a.aspect)
        plan = compile_script(script, tr, beats, theme.name)
        dur = round(beats.beats[-1].end + 0.6, 2)
        data = resolve_composition(plan, tr, beats, theme, a.aspect, dur, None, media={}, envelope={"dt": 0.04, "v": [0.5] * int(dur / 0.04)}, language="en")
        data["icons"] = {}
        d = Path(a.out) / f"{name}-{a.aspect.replace(':', 'x')}"
        idx = write_composition(d / "comp", data, theme)
        times = [round(0.3 + k * 1.1, 2) for k in range(int((dur - 0.3) / 1.1))][:12]
        frames = snapshot(idx.parent, d / "snap", times)
        w, h = (320, 180) if a.aspect == "16:9" else (180, 320)
        cols = 4
        rows = (len(frames) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows), "white")
        for i, f in enumerate(frames):
            sheet.paste(Image.open(f).convert("RGB").resize((w, h)), ((i % cols) * w, (i // cols) * h))
        sheet.save(d / "sheet.png")
        print(name, len(frames), "frames", d / "sheet.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
