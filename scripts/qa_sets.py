"""C2: every cartoon set, in every shape, under every camera and light, as contact sheets in dist/lab/ to look at.

    python scripts/qa_sets.py [--aspects 9:16,1:1,16:9] [--sets village,market] [--out dist/lab] [--gpu]

Each cell is one set with one character; two frames per scene (start and end of the camera move, where a shifted layer shows a gap at the edge).
The sheet rows are the sets, the columns are camera x light. Also prints a rough edge check: a gap shows the stage's own colour in the outer columns.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from vt.compose import showcase  # noqa: E402
from vt.render.hyperframes import snapshot  # noqa: E402

SETS = ["plain", "village", "market", "home", "office", "classroom", "street", "nature", "studio", "shop"]
CAMERAS = ["still", "push", "pull", "pan"]
LIGHTS = ["day", "sunset", "night"]
SIZE = {"9:16": (180, 320), "1:1": (240, 240), "16:9": (320, 180)}


def names_for(sets: list[str]) -> list[tuple[str, str, str, str]]:
    out = []
    for s in sets:
        for i, cam in enumerate(CAMERAS):
            for j, light in enumerate(LIGHTS if cam != "still" else ["day"]):
                out.append((f"{s}|{cam}|{light}", s, cam, light))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aspects", default="9:16,1:1,16:9")
    ap.add_argument("--sets", default="")
    ap.add_argument("--out", default=str(ROOT / "dist" / "lab"))
    ap.add_argument("--gpu", action="store_true", help="draw on a graphics card (not on the Windows PC)")
    a = ap.parse_args()
    sets = [s for s in SETS if not a.sets or s in a.sets.split(",")]
    cells = names_for(sets)
    for key, s, cam, light in cells:
        showcase.EL[key] = {"type": "cartoon", "set": s, "framing": "scene", "camera": cam, "lighting": light,
                            "cast": [{"who": "woman", "pose": "stand", "expression": "happy", "x": 0.5}], "bubble": "", "props": []}
    out_root = Path(a.out)
    out_root.mkdir(parents=True, exist_ok=True)
    bad = 0
    for aspect in a.aspects.split(","):
        work = out_root / f"qa-sets-{aspect.replace(':', 'x')}"
        idx, times = showcase.build(work, aspect, "paper", [c[0] for c in cells])
        both = [t for tt in times for t in (round(tt - 2.6, 2), tt)]
        frames = snapshot(idx.parent, work / "snap", both, gpu=a.gpu)
        w, h = SIZE[aspect]
        cols = max(len(CAMERAS) * len(LIGHTS) - 2, 1)
        for n, (key, s, cam, light) in enumerate(cells):
            for f in (frames[2 * n], frames[2 * n + 1]):
                im = np.asarray(Image.open(f).convert("RGB")).astype("int16")
                edge = np.concatenate([im[:, :3].reshape(-1, 3), im[:, -3:].reshape(-1, 3)])
                inner = im[:, im.shape[1] // 2 - 20: im.shape[1] // 2 + 20].reshape(-1, 3)
                if np.abs(edge.mean(0) - inner.mean(0)).sum() > 330:
                    bad += 1
                    print(f"possible edge gap: {aspect} {key} {Path(f).name}")
        for si, s in enumerate(sets):
            mine = [n for n, c in enumerate(cells) if c[1] == s]
            sheet = Image.new("RGB", (w * 2 * 5, h * ((len(mine) + 4) // 5)), "white")
            for k, n in enumerate(mine):
                for e in range(2):
                    sheet.paste(Image.open(frames[2 * n + e]).convert("RGB").resize((w, h)), ((k % 5) * 2 * w + e * w, (k // 5) * h))
            dest = out_root / f"sets-{s}-{aspect.replace(':', 'x')}.png"
            sheet.save(dest)
        print("sheets for", aspect, "in", out_root)
    print("edge-gap candidates:", bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
