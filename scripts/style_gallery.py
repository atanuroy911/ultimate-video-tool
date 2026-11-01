"""Three frames of one project in every film style, side by side: a quick way to judge all the looks.

    VT_PROJECTS=<lab projects> python scripts/style_gallery.py <project id> <out folder> [style ...]

The project is copied once per style (its plan and voice stay the same), the copy's theme set to style-<slug>, composed and snapshotted
(no full render). Writes <out>/<slug>.png and <out>/index.html.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    from PIL import Image

    from vt import styles
    from vt.compose import FORMATS
    from vt.pipeline import compose_all
    from vt.project import Project
    from vt.render.hyperframes import snapshot

    src = Project(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[3:] or [s["slug"] for s in styles.index()]
    aspect = src.meta().aspect
    dur = (src.transcript().kept() or [None])[-1].end if src.transcript().kept() else 10
    times = [0.4, dur * 0.4, dur * 0.8]
    done = []
    for slug in wanted:
        pid = f"{src.id}--{slug}"
        dst = src.dir.parent / pid
        if not dst.exists():
            shutil.copytree(src.dir, dst, ignore=shutil.ignore_patterns("exports", "composition", "snapshots", "cover_*", "qa_frames", "thumbs"))
        p = Project(pid)
        p.update_meta(theme=f"style-{slug}", id=pid)
        sf = p.scenes()
        p.save_scenes(sf.model_copy(update={"theme": f"style-{slug}"}))     # the plan carries the theme the composer draws, as the Studio sets it
        try:
            compose_all(p)
            files = snapshot(p.comp_dir / FORMATS[aspect]["tag"], p.dir / "snapshots", times)
        except Exception as e:                                                          # noqa: BLE001
            print(slug, "failed:", str(e)[:200], flush=True)
            continue
        ims = [Image.open(f).convert("RGB") for f in files]
        h = 640
        ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
        sheet = Image.new("RGB", (sum(i.width for i in ims) + 8 * (len(ims) - 1), h), "white")
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width + 8
        sheet.save(out / f"{slug}.png")
        done.append(slug)
        print(slug, "ok", flush=True)
    rows = "\n".join(f'<figure><img src="{s}.png" loading="lazy"><figcaption>{s}</figcaption></figure>' for s in done)
    (out / "index.html").write_text(f"""<!doctype html><meta charset="utf-8"><title>Style gallery</title>
<style>body{{font:14px system-ui;background:#111;color:#eee;margin:16px}}figure{{margin:0 0 18px}}img{{max-width:100%;border-radius:8px}}</style>
{rows}""", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
