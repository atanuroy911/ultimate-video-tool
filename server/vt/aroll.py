"""A-roll: the speaker's own picture.

When the file a project was made from is a video (a talking head, an interview, a screen recording with a voice), its picture is kept. It is cut with exactly the same cuts as the voice
(silences, fillers and the owner's own cuts), so picture time = edited voice time, and stored as `media/aroll.mp4` (no sound: the voice is the project's own cut audio, so picture and
sound cannot drift apart). The item is marked `role: a_roll`, so the planners never use it as B-roll; `apply_speaker` decides which scenes show the speaker (the opening, and every scene
whose only picture would be a word or a sticker) and gives them a gentle punch-in now and then, never twice in a row. The face position of the shot keeps the speaker in frame when a wide
picture is cropped to a tall one.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .schema import Backdrop, MediaItem, Scrim
from .util import CREATE_NO_WINDOW, find_tool, read_json

WEAK = {"keyword", "title", "sticker", "icon", "icon_row", "tag"}      # a word or a small picture: the speaker says it better than a graphic does
MAX_LONG_SIDE = 1920


def video_info(path: Path) -> Optional[dict]:
    """width, height, duration of the first real video stream (a cover picture inside an mp3 does not count), or None."""
    import json

    r = subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height,duration,codec_name:stream_disposition=attached_pic:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    try:
        j = json.loads(r.stdout or "{}")
    except ValueError:
        return None
    for st in j.get("streams", []):
        if st.get("disposition", {}).get("attached_pic") or not st.get("width"):
            continue
        dur = float(st.get("duration") or j.get("format", {}).get("duration") or 0)
        if dur > 0.2:
            return {"width": int(st["width"]), "height": int(st["height"]), "duration": dur}
    return None


def filter_script(keep: list[tuple[float, float]], long_side: int, width: int, height: int) -> str:
    """ffmpeg filter graph that plays the kept ranges one after the other, at 30 fps and at most `long_side` pixels on the long side."""
    scale = ""
    if max(width, height) > long_side:
        scale = f",scale='if(gte(iw,ih),{long_side},-2)':'if(gte(iw,ih),-2,{long_side})'"
    parts, names = [], []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,fps=30{scale},format=yuv420p[v{i}]")
        names.append(f"[v{i}]")
    parts.append(f"{''.join(names)}concat=n={len(keep)}:v=1:a=0[out]")
    return ";\n".join(parts)


def track_face(video: Path, duration: float, tmp: Path, n: int = 8) -> tuple[list[list[float]], Optional["np.ndarray"]]:
    """Where the speaker's face is, as the median box of the frames where one was found (a detector misses some frames). Returns ([box] or [], one frame for the contrast and subject guess)."""
    import numpy as np
    from PIL import Image

    from .director.media import detect_faces

    boxes, first = [], None
    for i in range(n):
        f = tmp / f"t{i}.png"
        subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{duration * (i + 0.5) / n:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=960:-2", str(f)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
        if not f.exists():
            continue
        im = np.asarray(Image.open(f).convert("RGB"))
        first = im if first is None else first
        fc = detect_faces(im, limit=1)
        if fc:
            boxes.append(fc[0])
    if len(boxes) < max(1, n // 4):                                # a face seen in one frame of eight is a false alarm
        return [], first
    med = np.median(np.array(boxes), axis=0)
    return [[round(float(v), 4) for v in med]], first


TEXT_ROWS = 0.4             # burned-in subtitles live in the bottom 40 % of the picture
TEXT_FRAMES = 0.1           # ... in at least a tenth of the sampled frames (clips often caption only their key lines)


def text_band(video: Path, duration: float, n: int = 16) -> Optional[float]:
    """Subtitles burned into the picture (a podcast clip that already has captions): bright text with a dark edge, low in the frame,
    in many frames. Returns where that band starts (0-1 from the top), or None. Our own captions would otherwise sit next to theirs,
    and a vertical crop cuts theirs off at both sides."""
    import numpy as np

    W, H = 192, 108
    tops = []
    for i in range(n):
        t = duration * (i + 0.5) / n
        raw = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={W}:{H}",
                              "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, creationflags=CREATE_NO_WINDOW).stdout
        if len(raw) != W * H:
            continue
        g = np.frombuffer(raw, dtype=np.uint8).reshape(H, W).astype(np.int16)
        bright = (g > 200)[:, int(W * 0.15):int(W * 0.85)].mean(axis=1)                 # rows, centre of the picture (where captions are set)
        lo = int(H * (1 - TEXT_ROWS))
        rows = np.flatnonzero(bright[lo:] > 0.05) + lo
        if 3 <= len(rows) <= 18 and bright[lo:].max() > 0.08 and bright[:lo].mean() < 0.06:    # a band of white lettering low down (a shirt or a table is taller and wider)
            tops.append(rows.min() / H)
    if len(tops) < TEXT_FRAMES * n:
        return None
    return round(float(np.percentile(tops, 20)) - 0.02, 3)          # the higher lines too (two-line captions), with a little margin


SHOT_FPS = 2.0              # frames looked at per second to find camera cuts and faces
CUT_DIFF = 28.0             # mean grey-level change between two looks that means the camera cut
HIST_CUT = 0.35             # chi-square distance between colour histograms that means a cut even when the brightness barely moves
PAN_MARGIN = 0.08           # the face may sit this far (fraction of the width) from the crop centre before the camera pans


def head_centre(rgb: "np.ndarray", prefer_x: float = 0.5) -> tuple[float, float]:
    """Where a person's head is in a frame (0-1), from the people mask (one person when there are two), or (-1, -1)."""
    import numpy as np

    from . import people as PE

    try:
        g = _one_person(PE.to_grid(PE.person_mask(rgb, None, True)), prefer_x)
    except Exception:
        return -1.0, -1.0
    ys, xs = np.nonzero(g)
    if len(xs) < 6:
        return -1.0, -1.0
    top = ys <= ys.min() + max(2, int(0.25 * (ys.max() - ys.min() + 1)))                  # the top quarter of the person: the head, not the arms
    return round(float((np.median(xs[top]) + 0.5) / PE.GW), 3), round(float((ys[top].mean() + 0.5) / PE.GH), 3)


def camera_cuts(frames: "np.ndarray") -> list[int]:
    """Frame indices where the camera cuts: a big change in mean grey, or in the colour histogram (chi-square distance) above an
    adaptive threshold (mean + 3σ of the clip's own distances), the histogram test Google's AutoFlip uses for shot boundaries."""
    import numpy as np

    n = len(frames)
    if n < 2:
        return [0, n]
    grey = frames.mean(axis=3)
    grey_jump = np.array([float(np.abs(grey[i] - grey[i - 1]).mean()) for i in range(1, n)])
    hists = np.stack([np.concatenate([np.histogram(frames[i, :, :, c], bins=16, range=(0, 256))[0] for c in range(3)]).astype(float) for i in range(n)])
    hists /= hists.sum(axis=1, keepdims=True) + 1e-9
    chi = np.array([float(((hists[i] - hists[i - 1]) ** 2 / (hists[i] + hists[i - 1] + 1e-9)).sum()) for i in range(1, n)])
    adaptive = chi.mean() + 3 * chi.std() if n > 8 else HIST_CUT
    cut = [i for i in range(1, n) if grey_jump[i - 1] > CUT_DIFF or chi[i - 1] > max(HIST_CUT, adaptive)]
    return [0] + cut + [n]


def smooth_pan(centres: list[Optional[tuple[float, float]]]) -> tuple[float, float, float]:
    """(hx at the start, hy, hx at the end) of a shot from its per-frame face centres: the L1-optimal camera path
    (vt/camerapath.py) keeps the face inside the crop and moves only in a few steady pans; the ends of that path are what the
    renderer glides between. -1 when no face at all."""
    import numpy as np

    from .camerapath import optimal_path

    xs = np.array([c[0] if c else np.nan for c in centres], dtype=float)
    ys = [c[1] for c in centres if c]
    if not ys:
        return -1.0, -1.0, -1.0
    path = optimal_path(xs, PAN_MARGIN)
    return float(path[0]), float(np.median(ys)), float(path[-1])


def shot_track(video: Path, duration: float) -> list[list[float]]:
    """The camera shots of a video and where the face is in each: [[t0, t1, hx, hy, hx_end], ...] (fractions of the picture, -1 when no face
    was seen twice). A podcast cuts between the host, the guest and a wide shot; a vertical crop must jump to the face at every cut, and
    within a shot it pans steadily from hx to hx_end when the speaker drifts (never a frame-by-frame chase)."""
    import numpy as np

    from .director.media import detect_faces

    W, H = 480, 270
    raw = subprocess.run([find_tool("ffmpeg"), "-v", "error", "-i", str(video), "-vf", f"fps={SHOT_FPS},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, creationflags=CREATE_NO_WINDOW).stdout
    n = len(raw) // (W * H * 3)
    if n == 0:
        return []
    frames = np.frombuffer(raw[: n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)
    cuts = camera_cuts(frames)
    shots, prev_x = [], 0.5
    for a, b in zip(cuts, cuts[1:]):
        centres: list[Optional[tuple[float, float]]] = []
        for i in range(a, b):
            f = detect_faces(frames[i], limit=1)
            centres.append((f[0][0] + f[0][2] / 2, f[0][1] + f[0][3] / 2) if f else None)
        seen = [c for c in centres if c]
        if len(seen) >= 2 or (b - a == 1 and seen):
            hx, hy, hx_end = smooth_pan(centres)
        else:                                                      # no face seen (sunglasses, profile, a small face in a wide shot): the head of the person
            hx, hy = head_centre(frames[(a + b) // 2], prev_x)
            hx_end = hx
        if hx >= 0:
            prev_x = hx
        shots.append([round(a / SHOT_FPS, 2), round(min(duration, b / SHOT_FPS), 2), round(hx, 3), round(hy, 3), round(hx_end, 3)])
    return shots


def build(project, progress=None, force: bool = False) -> Optional[MediaItem]:
    """Cut the speaker's picture with the project's cuts and put it in the media bin as the A-roll. Returns the item, or None when the input has no picture."""
    from .director.media import detect_faces, face_focus, media_dir, probe, subject_position
    from .util import file_hash

    src = project.input_audio
    if not src.exists():
        return None
    info = video_info(src)
    if info is None:
        return None
    cuts = project.cuts()
    if cuts is None or not cuts.keep:
        return None
    h = file_hash(src, project.cuts_path, extra=f"aroll-v3|{MAX_LONG_SIDE}|{project.meta().options.recording_edit}")
    meta = project.meta()
    have = next((m for m in meta.media if m.id == "aroll"), None)
    if have and not force and project.stage_done("aroll", h) and (project.dir / have.file).exists():
        return have
    import tempfile

    out = media_dir(project) / "aroll.mp4"
    if meta.options.recording_edit != 'auto' and len(cuts.keep)==1 and abs(cuts.keep[0][0])<.001 and abs(cuts.keep[0][1]-cuts.source_duration)<.05:
        import shutil
        # Retain the original recording, including its frame rate and tiny text.
        out=out.with_suffix(src.suffix.lower());shutil.copyfile(src,out)
        item=MediaItem(id='aroll',file=str(out.relative_to(project.dir)).replace('\\','/'),kind='video',role='a_roll',caption='Original screen recording',
            width=info['width'],height=info['height'],duration=info['duration'],source='a-roll')
        meta.media=[m for m in meta.media if m.id!='aroll']+[item];project.save_meta(meta)
        project.mark_stage('aroll',h,seconds=item.duration,faces=0)
        return item
    with tempfile.TemporaryDirectory(dir=project.dir) as d:       # on the project's own drive: a file cannot be moved from C:\ temp to a project on E:\ (WinError 17)
        script = Path(d) / "cut.txt"
        tmp = Path(d) / "aroll.mp4"                                # written here first, moved into the media bin only when the cut succeeded
        script.write_text(filter_script([(a, b) for a, b in cuts.keep], MAX_LONG_SIDE, info["width"], info["height"]), encoding="utf-8")
        from . import gpu
        encoder_args = ["-c:v", "h264_nvenc", *gpu.nvenc_device(), "-preset", "p4", "-cq", "21"] if gpu.has_nvenc() else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
        cmd = [find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-/filter_complex", str(script), "-map", "[out]", "-an", *encoder_args,
               "-movflags", "+faststart", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0:                                      # older ffmpeg versions or nvenc failure falls back to libx264
            cmd_fb = [find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-filter_complex_script", str(script), "-map", "[out]", "-an",
                      "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart", str(tmp)]
            r = subprocess.run(cmd_fb, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if r.returncode != 0 or not tmp.exists():
            raise RuntimeError("the speaker's picture could not be cut: " + r.stderr[-200:])
        out.unlink(missing_ok=True)
        tmp.replace(out)
        faces, poster_im = track_face(out, info["duration"], Path(d))
        fx, fy = face_focus(faces, subject_position(poster_im) if poster_im is not None else (0.5, 0.4))
        band = text_band(out, info["duration"])
        shots = shot_track(out, info["duration"])
    got = probe(out)
    item = MediaItem(id="aroll", file="media/aroll.mp4", kind="video", role="a_roll", caption="A-roll (the speaker)", width=got["width"], height=got["height"],
                     duration=round(got["duration"], 2), fx=fx, fy=fy, faces=faces, source="a-roll", text_band=band, shots=shots)
    meta = project.meta()
    meta.media = [m for m in meta.media if m.id != "aroll"] + [item]
    project.save_meta(meta)
    project.mark_stage("aroll", h, seconds=item.duration, faces=len(faces))
    return item


def remove(project) -> None:
    meta = project.meta()
    gone = next((m for m in meta.media if m.id == "aroll"), None)
    if gone:
        (project.dir / gone.file).unlink(missing_ok=True)
        meta.media = [m for m in meta.media if m.id != "aroll"]
        project.save_meta(meta)


def person_grid(project, item: MediaItem, t0: float, t1: float, use_model: bool = True, faces_out: Optional[list] = None) -> list[str]:
    """Where the speaker is during [t0, t1] of the A-roll (three frames across the scene, merged): a coarse grid, see vt/people.py."""
    import tempfile

    import numpy as np
    from PIL import Image

    from . import people as PE
    from .director.media import detect_faces

    video = project.dir / item.file
    face = item.faces[0] if item.faces else None
    grids = []
    span = max(0.2, t1 - t0)
    with tempfile.TemporaryDirectory() as d:
        for i, q in enumerate((0.15, 0.5, 0.85)):
            f = Path(d) / f"p{i}.png"
            subprocess.run([find_tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{min(max(0.0, t0 + span * q), max(0.0, item.duration - 0.1)):.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=640:-2", str(f)], capture_output=True, creationflags=CREATE_NO_WINDOW)
            if f.exists():
                rgb = np.asarray(Image.open(f).convert("RGB"))
                here = detect_faces(rgb, limit=1)                # this frame's own face: a multi-camera podcast changes shot, and the clip's average face would put a phantom head into every frame
                if here and faces_out is not None:
                    faces_out.append(here[0])
                grids.append(PE.to_grid(PE.person_mask(rgb, here[0] if here else face, use_model)))
    return PE.pack(PE.union(grids)) if grids else []


def _one_person(g: "np.ndarray", prefer_x: float, gap: int = 2) -> "np.ndarray":
    """The mask of one person when the shot has several side by side (a podcast's wide shot): people are column groups separated by at
    least `gap` empty columns. The biggest wins (nearest the camera); within 15 % of each other, the one nearest `prefer_x` (0-1, where
    the speaker usually is)."""
    import numpy as np

    cols = np.flatnonzero(g.any(axis=0))
    if len(cols) == 0:
        return g
    groups, start = [], cols[0]
    for a, b in zip(cols, cols[1:]):
        if b - a > gap:
            groups.append((start, a))
            start = b
    groups.append((start, cols[-1]))
    if len(groups) == 1:
        return g
    mass = [int(g[:, a:b + 1].sum()) for a, b in groups]
    big = max(mass)
    cands = [grp for grp, m in zip(groups, mass) if m >= 0.85 * big]
    a, b = min(cands, key=lambda grp: abs((grp[0] + grp[1] + 1) / 2 / g.shape[1] - prefer_x))
    out = np.zeros_like(g)
    out[:, a:b + 1] = g[:, a:b + 1]
    return out


def face_focus_in_scene(faces: list[list[float]], src_aspect: float) -> Optional[tuple[float, float]]:
    """The crop for a scene from the faces seen in it (median centre): better than the body's outline, which spreads with the arms.
    Needs a face in at least two of the sampled frames: one lone detection is often a face in a poster on the wall."""
    if len(faces) < 2:
        return None
    import statistics

    hx = statistics.median(f[0] + f[2] / 2 for f in faces)
    hy = statistics.median(f[1] + f[3] / 2 for f in faces)
    vw = min(1.0, (9 / 16) / max(src_aspect, 1e-6))
    fx = 0.5 if vw >= 0.999 else (hx - vw / 2) / (1 - vw)
    return round(float(min(1.0, max(0.0, fx))), 3), round(float(min(0.85, max(0.15, hy))), 3)


def head_focus(rows: list[str], src_aspect: float, fallback: tuple[float, float]) -> tuple[float, float]:
    """Where to point the crop for this scene: the head of the person in the scene's own mask (the speaker moves, leans in and turns between scenes).
    Returns (fx, fy) as the CSS object-position that centres the head in the tallest crop (9:16) and the head's height for the punch-in."""
    import numpy as np

    from . import people as PE

    if not rows:
        return fallback
    g = PE.unpack(rows)
    g = _one_person(g, fallback[0])                 # a wide two-shot: frame one person, never the empty space between them
    ys, xs = np.nonzero(g)
    if len(xs) < 6:
        return fallback
    top = ys <= ys.min() + max(2, int(0.35 * (ys.max() - ys.min() + 1)))            # the upper third of the person: the head
    hx, hy = ((xs[top].min() + xs[top].max()) / 2 + 0.5) / PE.GW, (ys[top].mean() + 0.5) / PE.GH          # the middle of the head's width (a profile has more hair than face: the mean would lean to the back of the head)
    vw = min(1.0, (9 / 16) / max(src_aspect, 1e-6))
    fx = 0.5 if vw >= 0.999 else (hx - vw / 2) / (1 - vw)
    return round(float(min(1.0, max(0.0, fx))), 3), round(float(min(0.85, max(0.15, hy))), 3)


def scene_span(sc, bmap) -> Optional[tuple[float, float]]:
    bs = [bmap[b] for b in sc.beats if b in bmap]
    return (min(b.start for b in bs), max(b.end for b in bs)) if bs else None


def apply_speaker(sf, project, beats, aspect: str, item: Optional[MediaItem] = None, force: Optional[set] = None) -> int:
    """Show the speaker where nothing better illustrates the words. Works on the plan in place; returns how many scenes now show the speaker.

    * the first scene always shows the speaker (a talking head opens on the person);
    * a scene whose only pictures are words or small stickers shows the speaker, with its first word or sticker as text over the picture;
    * never more than two speaker scenes in a row (the picture has to change now and then);
    * a gentle punch-in on every other speaker scene, never on two in a row, and only when the face is in the shot (no crop that cuts the face)."""
    from .director import contrast as K
    from .schema import Scene

    item = item or next((m for m in project.meta().media if m.id == "aroll"), None)
    if item is None or not sf.scenes:
        return 0
    use_model = True
    try:
        from . import cutout

        use_model = cutout.available() and (cutout.ready() or bool(cutout.ensure_model()))
    except Exception:
        use_model = False                                                  # no model (offline): the body is estimated from the face box
    bmap = {b.id: b for b in beats.beats}
    run = 0
    punched_last = False
    shown = 0
    for i, sc in enumerate(sf.scenes):
        span = scene_span(sc, bmap)
        types = [getattr(e, "type", "") for e in sc.elements]
        weak = all(t in WEAK for t in types) and sc.backdrop is None
        want = span is not None and ((i == 0 or weak) and run < 2 or (force is not None and sc.id in force and sc.backdrop is None))
        if not want:
            run = 0
            continue
        t0, t1 = span
        screen = not item.faces                                         # no face anywhere: a screen or slide recording, whose own picture is the content
        keep = [] if screen else [e for e in sc.elements if getattr(e, "type", "") in ("keyword", "title", "sticker")][:1]
        sc.elements = keep
        sc.layout = "lower" if item.fy < 0.45 else "upper"             # the text goes where the face is not: in the band above the captions when the head is high in the picture, above the head when it is low
        punch = (not punched_last) and shown % 2 == 1 and bool(item.faces)
        # a person must stay clear: no wash over the picture, only a soft dark gradient under the captions (white captions and white words then read well on any shirt or wall)
        scrim = Scrim(ink="light", kind="gradient", strength=0.5, edge="bottom")
        seen: list = []
        grid = person_grid(project, item, t0, t1, use_model, faces_out=seen)
        fx, fy = face_focus_in_scene(seen, item.width / max(1, item.height)) or head_focus(grid, item.width / max(1, item.height), (item.fx, item.fy))
        sc.backdrop = Backdrop(media=item.id, motion="kenburns" if punch else "none", fx=fx, fy=fy, offset=round(t0, 3), scrim=scrim, person=grid or None)
        sc.archetype = "speaker"
        punched_last = punch
        run += 1
        shown += 1
    return shown


def keep_screen_clear(sf, project) -> int:
    """A screen or slide recording (no face in the speaker's picture) is the content itself: on every scene that shows it, nothing but the
    captions. Later passes may have added a word or a sticker after the speaker was chosen; this runs last, just before the plan is saved."""
    item = next((m for m in project.meta().media if m.id == "aroll" and m.role == "a_roll"), None)
    if item is None or item.faces:
        return 0
    n = 0
    for sc in sf.scenes:
        if sc.backdrop is not None and sc.backdrop.media == item.id and sc.elements:
            sc.elements = []
            n += 1
    return n
