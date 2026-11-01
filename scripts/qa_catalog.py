"""Real compatibility check of every catalogue entry with the app's own pipeline: videos are added to a project's media bin (normalised by ffmpeg), music is installed
and resolved the way the export mixer does, speech is decoded as a recording. Needs the network (it downloads each file). Run with VT_DATA pointing at a scratch folder."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vt import paths  # noqa: E402
from vt.director import catalog as C  # noqa: E402
from vt.director import media as M  # noqa: E402
from vt.project import Project  # noqa: E402
from vt.render.mux import resolve_music  # noqa: E402


def main() -> int:
    es = [e for e in C.load() if e.get("status") == "ok"]
    p = Project("reference") if Project("reference").exists() else None
    if p is None:
        print("needs a project named 'reference' in the projects folder")
        return 2
    bad = 0
    for e in es:
        t0 = time.time()
        try:
            if e["kind"] == "video":
                m = C.install_media(p, e["id"])
                info = M.probe(p.dir / m.file)
                ok = m.width > 0 and m.height > 0 and 0.3 < m.duration < 600 and info["width"] == m.width
                msg = f"{m.width}x{m.height} {m.duration}s faces={len(m.faces)} focus=({m.fx:.2f},{m.fy:.2f})"
            elif e["kind"] == "audio" and e["role"] in ("music", "sfx"):
                mid = C.install_music(e["id"])
                path = resolve_music(mid)
                inf = C.ffprobe(path)
                ok = bool(path and path.exists() and inf["audio"] and C.decodes(path) is None)
                msg = f"{mid} {inf['audio']['codec']} {inf['audio']['sample_rate']}Hz {inf['duration']}s"
            else:
                import tempfile

                with tempfile.TemporaryDirectory() as d:
                    f = Path(d) / "x.mp3"
                    C.download(e["url"], f, 20)
                    inf = C.ffprobe(f)
                    ok = inf["audio"] and C.decodes(f, 30) is None
                    msg = f"speech {inf['audio']['codec']} {inf['audio']['sample_rate']}Hz {inf['duration']}s"
        except Exception as ex:  # noqa: BLE001
            ok, msg = False, f"{type(ex).__name__}: {ex}"
        bad += 0 if ok else 1
        print(f"{'ok ' if ok else 'BAD'} {e['kind']:5} {e['id'][:46]:46} {msg} ({time.time() - t0:.0f}s)", flush=True)
    print(f"\n{len(es) - bad}/{len(es)} entries work with the pipeline")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
