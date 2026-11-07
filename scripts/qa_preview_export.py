"""C9: the Studio preview is a snapshot of the page; the export is the MP4. For three styles, take 5 moments each from both and compare.

    python scripts/qa_preview_export.py [--out dist/lab/c9] [--styles paper,minimal,midnight]

Writes side-by-side sheets (snapshot left, MP4 frame right, difference far right) and prints the mean difference per moment.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from vt.compose import showcase  # noqa: E402
from vt.render.hyperframes import render_silent, snapshot  # noqa: E402

PARTS = ["cartoon_market", "cartoon_nature", "ring", "steps", "stat_row"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "lab" / "c9"))
    ap.add_argument("--styles", default="paper,minimal,midnight")
    ap.add_argument("--aspect", default="16:9")
    a = ap.parse_args()
    out = Path(a.out)
    worst = 0.0
    for style in a.styles.split(","):
        work = out / style
        try:
            idx, times = showcase.build(work, a.aspect, style, PARTS)
        except FileNotFoundError as e:
            print("skipped", style, e)
            continue
        snaps = snapshot(idx.parent, work / "snap", times, gpu=False)
        mp4 = render_silent(idx.parent, work / "out.mp4", gpu=False)
        rows = []
        for n, t in enumerate(times):
            png = work / f"mp4-{n}.png"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(png)], check=True)
            s = Image.open(snaps[n]).convert("RGB")
            m = Image.open(png).convert("RGB").resize(s.size)
            diff = np.abs(np.asarray(s).astype("int16") - np.asarray(m).astype("int16")).sum(axis=2)
            mean = float(diff.mean() / 3)
            worst = max(worst, mean)
            print(f"{style} t={t}: mean difference {mean:.2f} of 255, {100 * float((diff > 90).mean()):.2f}% of pixels differ a lot")
            vis = Image.fromarray(np.clip(diff * 2, 0, 255).astype("uint8")).convert("RGB")
            w, h = s.size
            row = Image.new("RGB", (w * 3, h))
            for k, im in enumerate((s, m, vis)):
                row.paste(im, (k * w, 0))
            rows.append(row.resize((row.width // 3, row.height // 3)))
        sheet = Image.new("RGB", (rows[0].width, rows[0].height * len(rows)))
        for i, r in enumerate(rows):
            sheet.paste(r, (0, i * r.height))
        sheet.save(out / f"c9-{style}.png")
    print("worst mean difference", round(worst, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
