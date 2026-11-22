"""Fast render for long recordings (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C11).

Most of a long talk is the speaker's own recording with captions over it. Capturing every one of those frames in Chrome took 2 h 15 m for a
14-minute talk on a 6 GB laptop (2026-11-22), while the encoder (NVENC) waited. Here the timeline is split into runs:

* plain runs: a scene that shows only the A-roll (backdrop media 'aroll', no element, no shot, no layer over it). ffmpeg cuts the already-cut
  `media/aroll.mp4` and burns the captions as ASS subtitles in the theme's caption colours and font (from the composition's own fonts folder);
* designed runs: everything else, drawn by the renderer as before, one clipped page per run (`window.__VT_WINDOW`, server/renderer/runtime/vt.js).

The pieces are joined and encoded once. Voice, music and sounds are mixed afterwards over the whole, exactly as for a normal render.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

from ..util import CREATE_NO_WINDOW, find_tool

MIN_PLAIN = 3.0          # a plain stretch shorter than this is drawn with its neighbours (no tiny pieces)
MIN_SHARE = 0.4          # use the fast path only when at least this share of the video is plain A-roll


def _plain(sc: dict, layer_spans: list[tuple[float, float]]) -> bool:
    bd = sc.get("backdrop") or {}
    if bd.get("media") != "aroll" or sc.get("elements") or sc.get("shot"):
        return False
    s, e = float(sc["start"]), float(sc["end"])
    return not any(a < e and b > s for a, b in layer_spans)


def runs(data: dict) -> list[tuple[str, float, float]]:
    """[(kind, start, end)] covering 0..duration; kind is 'plain' or 'designed'."""
    dur = float(data["duration"])
    spans = []
    for layer in data.get("layers") or []:
        for c in layer.get("clips", []) if isinstance(layer, dict) else []:
            try:
                spans.append((float(c["start"]), float(c["start"]) + float(c.get("dur") or c.get("duration") or 0)))
            except (KeyError, TypeError, ValueError):
                continue
    out: list[list] = []
    for sc in sorted(data.get("scenes", []), key=lambda s: float(s["start"])):
        kind = "plain" if _plain(sc, spans) else "designed"
        s, e = float(sc["start"]), float(sc["end"])
        if out and out[-1][0] == kind and abs(out[-1][2] - s) < 0.05:
            out[-1][2] = e
        else:
            out.append([kind, s, e])
    if not out:
        return [("designed", 0.0, dur)]
    out[0][1], out[-1][2] = 0.0, dur                                     # no gap at the ends
    for a, b in zip(out, out[1:]):                                       # no gap between runs: the earlier run ends where the next starts
        a[2] = b[1]
    for r in out:                                                         # a short plain stretch is drawn with its neighbours
        if r[0] == "plain" and r[2] - r[1] < MIN_PLAIN:
            r[0] = "designed"
    merged: list[list] = []
    for r in out:
        if merged and merged[-1][0] == r[0]:
            merged[-1][2] = r[2]
        else:
            merged.append(list(r))
    return [(k, round(s, 3), round(e, 3)) for k, s, e in merged]


def plain_share(rs: list[tuple[str, float, float]]) -> float:
    total = sum(e - s for _, s, e in rs) or 1.0
    return sum(e - s for k, s, e in rs if k == "plain") / total


def _ass_colour(hex_colour: str, alpha: int = 0) -> str:
    h = (hex_colour or "#ffffff").lstrip("#")
    if len(h) != 6:
        h = "ffffff"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass(captions: list[dict], theme: dict, fmt: dict, t0: float, t1: float) -> str:
    """The captions between t0 and t1 as ASS, times from t0, in the theme's caption colours (a box behind the words, highlighted words in the
    highlight colour). Close to the runtime's caption, not identical: no rounded corners or reveal animation."""
    W, H = int(fmt["width"]), int(fmt["height"])
    col = theme.get("color") or {}
    cap = theme.get("caption") or {}
    font = ((theme.get("font") or {}).get("caption") or ["Inter"])[0]
    landscape = W > H
    size = int(round(float(cap.get("size", 58)) * (0.8 if landscape else 1.0)))
    bottom = int((cap.get("safe_bottom") or {}).get("landscape" if landscape else "portrait", 64 if landscape else 300))
    ink, bg, hl = col.get("caption_ink", "#1a1a1a"), col.get("caption_bg", "#ffffff"), col.get("highlight_bg", "#f26a1f")
    bold = -1 if int(cap.get("weight", 700)) >= 600 else 0
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{size},{_ass_colour(ink)},{_ass_colour(ink)},{_ass_colour(bg)},{_ass_colour(bg)},{bold},0,0,0,100,100,0,0,3,{max(8, size // 3)},0,2,"
        f"{W // 10},{W // 10},{bottom + size // 2},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines = []
    for c in captions:
        s, e = float(c["start"]), float(c["end"])
        if e <= t0 or s >= t1:
            continue
        words = []
        for w in c.get("words", []):
            text = str(w.get("text", "")).replace("{", "(").replace("}", ")").replace("\\", "/")
            words.append(f"{{\\c{_ass_colour(hl)}}}{text}{{\\c{_ass_colour(ink)}}}" if w.get("hl") else text)
        lines.append(f"Dialogue: 0,{_ass_time(max(s, t0) - t0)},{_ass_time(min(e, t1) - t0)},Cap,,0,0,0,,{' '.join(words)}")
    return "\n".join(head + lines) + "\n"


def _encoder(gpu: bool) -> list[str]:
    from .. import gpu as G

    if gpu and G.has_nvenc():
        return ["-c:v", "h264_nvenc", *G.nvenc_device(), "-preset", "p4", "-cq", "21", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def plain_piece(aroll: Path, comp_dir: Path, data: dict, t0: float, t1: float, out: Path, *, gpu: bool = True, track: Optional[Path] = None) -> Path:
    """The A-roll from t0 to t1 (it is already cut to the edited voice: video time = media time), filled to the frame, captions burned in."""
    fmt = data["format"]
    W, H, fps = int(fmt["width"]), int(fmt["height"]), int(fmt.get("fps", 30))
    sub = out.with_suffix(".ass")
    sub.write_text(ass(data.get("captions") or [], data.get("theme") or {}, fmt, t0, t1), encoding="utf-8")
    dur = t1 - t0
    esc = lambda p: str(p).replace("\\", "/").replace(":", "\\:")             # noqa: E731 — ffmpeg filter paths
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},"
          f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},"
          f"ass='{esc(sub)}':fontsdir='{esc(comp_dir / 'fonts')}'")
    cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(aroll), "-an", "-vf", vf,
           *_encoder(gpu), "-r", str(fps), str(out)]
    if track is not None:                                                # the runtime's own captions, keyed out of green
        base = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps},"
                f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setpts=PTS-STARTPTS")
        fc = (f"[0:v]{base}[v];[1:v]fps={fps},trim=duration={dur:.3f},setpts=PTS-STARTPTS,colorkey=0x00ff00:0.32:0.06,format=yuva420p[c];"
              f"[v][c]overlay=0:0:format=auto,format=yuv420p[o]")
        cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(aroll),
               "-ss", f"{t0:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", str(track), "-an", "-filter_complex", fc, "-map", "[o]",
               *_encoder(gpu), "-r", str(fps), "-t", f"{dur:.3f}", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError("the speaker's stretch could not be cut: " + r.stderr[-300:])
    return out


def _prune(html: str, t0: float, t1: float, margin: float = 1.0) -> str:
    """The page's data (window.__VT__) with only the scenes, captions and layer clips near the window. Times stay as they are (the runtime
    shifts the whole timeline), so nothing inside a kept scene changes."""
    import json

    key = "window.__VT__ = "
    a = html.find(key)
    if a < 0:
        return html
    b = html.find("</script>", a)
    body = html[a + len(key):b].rstrip().rstrip(";")
    try:
        d = json.loads(body)
    except ValueError:
        return html
    near = lambda s, e: float(e) > t0 - margin and float(s) < t1 + margin              # noqa: E731
    d["scenes"] = [sc for sc in d.get("scenes", []) if near(sc["start"], sc["end"])]
    d["captions"] = [c for c in d.get("captions", []) if near(c["start"], c["end"])]
    d["cues"] = []                                                       # sounds are mixed later, not drawn
    for layer in d.get("layers") or []:
        if isinstance(layer, dict) and isinstance(layer.get("clips"), list):
            layer["clips"] = [c for c in layer["clips"] if near(c.get("start", 0), float(c.get("start", 0)) + float(c.get("dur") or c.get("duration") or 0))]
    return html[:a] + key + json.dumps(d, ensure_ascii=False) + ";" + html[b:]


def designed_piece(comp_dir: Path, t0: float, t1: float, out: Path, *, fps: int, quality: str, gpu: bool,
                   on_progress: Optional[Callable[[float, str], None]] = None) -> Path:
    """The composition from t0 to t1, drawn by the renderer from a clipped copy of the page."""
    from .hyperframes import render_silent

    page = comp_dir / f"window-{int(t0 * 1000)}.html"
    html = (comp_dir / "index.html").read_text(encoding="utf-8")
    tag = f"<script>window.__VT_WINDOW={{start:{t0},end:{t1}}};</script>"
    import re

    html = _prune(html, t0, t1)                                          # a frame costs more the bigger the page: keep only what this window shows
    html = re.sub(r'(<div[^>]*id="root"[^>]*?data-duration=")[^"]*(")', lambda m: f"{m.group(1)}{t1 - t0:.3f}{m.group(2)}", html, count=1)   # the renderer reads the length from the page itself
    at = html.find("<script")
    page.write_text(html[:at] + tag + html[at:] if at >= 0 else tag + html, encoding="utf-8")
    try:
        render_silent(comp_dir, out, fps=fps, quality=quality, gpu=gpu, on_progress=on_progress, page=page.name)
    finally:
        page.unlink(missing_ok=True)
    return out


def join(pieces: list[Path], out: Path, *, fps: int, gpu: bool = True) -> Path:
    """One silent video from the pieces, encoded once (the pieces come from two encoders)."""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in pieces), encoding="utf-8")
    cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-an", "-r", str(fps), *_encoder(gpu), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    lst.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError("the pieces could not be joined: " + r.stderr[-300:])
    return out


def render_silent_fast(project, comp_dir: Path, data: dict, out: Path, *, fps: int, quality: str, gpu: bool,
                       on_progress: Callable[[float, str], None] = lambda f, m: None) -> Optional[Path]:
    """The whole silent video by runs, or None when this video is not mostly plain A-roll (the caller then renders it the usual way)."""
    aroll = project.dir / "media" / "aroll.mp4"
    if not aroll.exists():
        return None
    rs = runs(data)
    if plain_share(rs) < MIN_SHARE:
        return None
    work = out.parent / (out.stem + ".pieces")
    work.mkdir(parents=True, exist_ok=True)
    total = sum(e - s for _, s, e in rs) or 1.0
    track = None
    try:                                                                 # captions of the plain stretches, drawn once each by the runtime
        plain = [(s, e) for k, s, e in rs if k == "plain"]
        caps = [c for c in data.get("captions") or [] if any(float(c["end"]) > s and float(c["start"]) < e for s, e in plain)]
        on_progress(0.01, f"Drawing {len(caps)} caption lines")
        track = caption_track(caption_stills(comp_dir, data, caps, work), float(data["duration"]), data["format"], work)
    except Exception as e:                                               # noqa: BLE001 — the ASS captions below are close enough
        import logging
        logging.getLogger(__name__).warning("caption stills failed, using ASS captions: %s", e, exc_info=True)
    done = 0.0
    pieces = []
    for i, (kind, s, e) in enumerate(rs):
        piece = work / f"{i:03d}-{kind}.mp4"
        base = done / total
        share = (e - s) / total
        if kind == "plain":
            on_progress(base, f"Cutting the speaker's stretch {s:.0f}-{e:.0f} s")
            plain_piece(aroll, comp_dir, data, s, e, piece, gpu=gpu, track=track)
        else:
            designed_piece(comp_dir, s, e, piece, fps=fps, quality=quality, gpu=gpu,
                           on_progress=lambda f, m, b=base, sh=share: on_progress(b + sh * f, f"Drawing {s:.0f}-{e:.0f} s: {m}"))
        pieces.append(piece)
        done += e - s
    on_progress(0.98, "Joining the pieces")
    join(pieces, out, fps=fps, gpu=gpu)
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return out

GREEN = "#00ff00"


def caption_stills(comp_dir: Path, data: dict, captions: list[dict], work: Path) -> list[tuple[float, float, Path]]:
    """One picture of each caption line, drawn by the runtime itself (same font, box, border and highlight as the full render) over pure green,
    so ffmpeg can key the green out. Taken when the whole line is on screen. Returns [(start, end, png)]."""
    import re

    from .hyperframes import snapshot

    if not captions:
        return []
    index = comp_dir / "index.html"
    full = index.read_text(encoding="utf-8")
    html = _prune(full, 0.0, float(data["duration"]))
    key = "window.__VT__ = "
    a = html.find(key)
    if a >= 0:
        import json

        b = html.find("</script>", a)
        d = json.loads(html[a + len(key):b].rstrip().rstrip(";"))
        d["scenes"], d["layers"], d["cues"] = [], [], []
        html = html[:a] + key + json.dumps(d, ensure_ascii=False) + ";" + html[b:]
    style = (f"<style>html,body,#root{{background:{GREEN} !important}} #root > :not(.cap-layer){{display:none !important}}"
             f" #root .cap-layer{{display:block !important}}</style>")
    html = html.replace("</head>", style + "</head>", 1) if "</head>" in html else style + html
    times = [round(min(float(c["end"]) - 0.04, float(c["start"]) + 0.6), 3) for c in captions]
    shots: list[Path] = []
    backup = comp_dir / "index.full.html"
    backup.write_text(full, encoding="utf-8")
    try:
        index.write_text(html, encoding="utf-8")
        for i in range(0, len(times), 120):                               # a few hundred moments per call keeps the command line short
            got = snapshot(comp_dir, work / f"caps-{i:05d}", times[i:i + 120])
            got = sorted(got, key=lambda p: int(re.search(r"frame-(\d+)", p.name).group(1)))      # frame-10 comes before frame-100 by number, not by text
            shots.extend(got[: len(times[i:i + 120])])
    finally:
        index.write_text(full, encoding="utf-8")
        backup.unlink(missing_ok=True)
    return [(float(c["start"]), float(c["end"]), p) for c, p in zip(captions, shots)]


def caption_track(stills: list[tuple[float, float, Path]], duration: float, fmt: dict, work: Path) -> Path:
    """A lossless green-screen video of the captions over the whole video: each still from its line's start to the next line's start."""
    from PIL import Image

    W, H = int(fmt["width"]), int(fmt["height"])
    blank = work / "green.png"
    Image.new("RGB", (W, H), GREEN).save(blank)
    seq: list[tuple[Path, float]] = []
    t = 0.0
    for s, e, p in sorted(stills, key=lambda x: x[0]):
        if s > t + 0.01:
            seq.append((blank, s - t))
            t = s
        seq.append((p, max(0.04, e - t)))
        t = e
    if duration > t:
        seq.append((blank, duration - t))
    lst = work / "captions.txt"
    nl = chr(10)
    lst.write_text("".join(f"file '{p.as_posix()}'{nl}duration {d:.3f}{nl}" for p, d in seq) + f"file '{seq[-1][0].as_posix()}'{nl}", encoding="utf-8")
    out = work / "captions.mkv"
    cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"scale={W}:{H},fps=30",
           "-c:v", "ffv1", "-pix_fmt", "rgb24", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError("the caption track could not be made: " + r.stderr[-300:])
    return out
