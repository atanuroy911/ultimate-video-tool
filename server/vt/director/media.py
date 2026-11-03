"""The project's media bin: pictures, GIFs and video clips the user drops in (or downloads from a stock site).

Everything is normalised once on the way in so rendering is deterministic and fast:
  images  -> capped to 2400 px, subject position (fx, fy) estimated
  GIFs    -> looping H.264 MP4 (seeking a GIF frame by frame is not reliable)
  videos  -> H.264 MP4, no audio (the voice is the audio), max 1080 px, constant 30 fps (frame-accurate seeking)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from ..schema import MediaItem
from ..util import CREATE_NO_WINDOW, find_tool, slugify

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}
GIF_EXT = {".gif"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | GIF_EXT
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac"}
MAX_IMAGE = 2400
MAX_BYTES = 400 * 1024 * 1024


class MediaError(ValueError):
    pass


def media_dir(project) -> Path:
    d = project.dir / "media"
    d.mkdir(exist_ok=True)
    return d


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise MediaError("ffmpeg could not read this file: " + (r.stderr or "")[-200:])
    return r.stdout


def probe(path: Path) -> dict:
    """width, height, duration of a video/gif (ffprobe)."""
    out = subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout
    try:
        j = json.loads(out or "{}")
        st = (j.get("streams") or [{}])[0]
        dur = float(st.get("duration") or j.get("format", {}).get("duration") or 0)
        return {"width": int(st.get("width", 0)), "height": int(st.get("height", 0)), "duration": dur}
    except (ValueError, KeyError, IndexError):
        raise MediaError("not a readable picture or video")


def subject_position(rgb: np.ndarray) -> tuple[float, float]:
    """Where the subject probably is (0-1, 0-1): centre of detail (edges + colour saturation + skin-like tones). Falls back to the centre."""
    g = rgb.astype("float32").mean(axis=2)
    gy, gx = np.abs(np.diff(g, axis=0))[:, :-1], np.abs(np.diff(g, axis=1))[:-1, :]
    edge = gy + gx
    mx, mn = rgb.max(axis=2).astype("float32"), rgb.min(axis=2).astype("float32")
    sat = ((mx - mn) / (mx + 1.0))[:-1, :-1]
    r, gg, b = rgb[..., 0].astype("float32"), rgb[..., 1].astype("float32"), rgb[..., 2].astype("float32")
    skin = ((r > 95) & (gg > 40) & (b > 20) & (r > gg) & (r > b) & ((mx - mn) > 15))[:-1, :-1].astype("float32")
    w = edge / (edge.max() + 1e-6) + 0.6 * sat + 0.8 * skin
    w = np.clip(w - np.median(w), 0, None)
    if w.sum() < 1e-6:
        return 0.5, 0.5
    h, wd = w.shape
    ys, xs = np.mgrid[0:h, 0:wd]
    cy, cx = (w * ys).sum() / w.sum() / h, (w * xs).sum() / w.sum() / wd
    return round(float(np.clip(cx, 0.2, 0.8)), 3), round(float(np.clip(cy, 0.2, 0.8)), 3)


_cascade = {}


def detect_faces(rgb: np.ndarray, limit: int = 4) -> list[list[float]]:
    """Faces in a picture as [x, y, w, h] fractions (biggest first), by OpenCV's frontal-face cascade. No faces, or no OpenCV: an empty list."""
    try:
        import cv2
    except ImportError:
        return []
    if "c" not in _cascade:
        _cascade["c"] = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    casc = _cascade["c"]
    if casc.empty():
        return []
    g = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY)
    h, w = g.shape
    k = 480 / max(h, w)
    if k < 1:
        g = cv2.resize(g, (int(w * k), int(h * k)))
        h, w = g.shape
    found = casc.detectMultiScale(cv2.equalizeHist(g), scaleFactor=1.1, minNeighbors=5, minSize=(max(24, int(0.07 * min(h, w))),) * 2)
    boxes = sorted(([x / w, y / h, bw / w, bh / h] for x, y, bw, bh in found), key=lambda b: -b[2] * b[3])
    return [[round(v, 4) for v in b] for b in boxes[:limit]]


def face_focus(faces: list[list[float]], fallback: tuple[float, float]) -> tuple[float, float]:
    """Where the camera should look: the middle of the biggest face, else the estimate from the picture's detail."""
    if not faces:
        return fallback
    x, y, w, h = faces[0]
    return round(min(0.85, max(0.15, x + w / 2)), 3), round(min(0.85, max(0.15, y + h / 2)), 3)


def _unique_id(project, stem: str) -> str:
    base = slugify(stem) or "media"
    base = re.sub(r"[^a-z0-9-]", "", base.lower())[:24] or "media"
    meta = project.meta()
    ids = {m.id for m in meta.media} | {m.id for m in meta.sounds}
    out, n = base, 2
    while out in ids:
        out = f"{base}-{n}"
        n += 1
    return out


def has_audio(path: Path) -> bool:
    out = subprocess.run([find_tool("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, creationflags=CREATE_NO_WINDOW).stdout
    return "audio" in out


def add_sound(project, src: Path, *, caption: str = "", source: str = "upload", credit: str = "", licence: str = "") -> MediaItem:
    """Copy an audio file (music, an effect, a voice-over) into the project as AAC, ready for a layer's audio track."""
    src = Path(src)
    if src.suffix.lower() not in AUDIO_EXT:
        raise MediaError(f"unsupported audio type '{src.suffix.lower()}'. Use {', '.join(sorted(AUDIO_EXT))}.")
    if not src.exists() or src.stat().st_size == 0:
        raise MediaError("the file is empty")
    if src.stat().st_size > MAX_BYTES:
        raise MediaError("the file is larger than 400 MB")
    meta = project.meta()
    base = re.sub(r"[^a-z0-9-]", "", (slugify(src.stem) or "sound").lower())[:24] or "sound"
    ids = {m.id for m in meta.media} | {m.id for m in meta.sounds}
    mid, n = base, 2
    while mid in ids:
        mid, n = f"{base}-{n}", n + 1
    out = media_dir(project) / f"{mid}.m4a"
    _run([find_tool("ffmpeg"), "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(out)])
    dur = float(subprocess.run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True,
                               creationflags=CREATE_NO_WINDOW).stdout.strip() or 0)
    if dur <= 0.05:
        out.unlink(missing_ok=True)
        raise MediaError("no sound was found in this file")
    item = MediaItem(id=mid, file=f"media/{out.name}", kind="audio", caption=caption or src.stem, duration=round(dur, 2), source=source, credit=credit, licence=licence)
    meta = project.meta()
    meta.sounds = [m for m in meta.sounds if m.id != item.id] + [item]
    project.save_meta(meta)
    return item


def remove_sound(project, media_id: str) -> bool:
    meta = project.meta()
    keep = [m for m in meta.sounds if m.id != media_id]
    if len(keep) == len(meta.sounds):
        return False
    gone = next(m for m in meta.sounds if m.id == media_id)
    (project.dir / gone.file).unlink(missing_ok=True)
    meta.sounds = keep
    project.save_meta(meta)
    return True


def add_media(project, src: Path, *, caption: str = "", tags: Optional[list[str]] = None, source: str = "upload", credit: str = "",
              licence: str = "", media_id: Optional[str] = None) -> MediaItem:
    """Copy a file into the project's media bin, normalising it. Returns the new bin entry."""
    from PIL import Image

    src = Path(src)
    ext = src.suffix.lower()
    if ext not in ALL_EXT:
        raise MediaError(f"unsupported file type '{ext}'. Use an image ({', '.join(sorted(IMAGE_EXT))}), a GIF, or a video ({', '.join(sorted(VIDEO_EXT))}).")
    if not src.exists() or src.stat().st_size == 0:
        raise MediaError("the file is empty")
    if src.stat().st_size > MAX_BYTES:
        raise MediaError("the file is larger than 400 MB")
    mid = media_id or _unique_id(project, src.stem)
    d = media_dir(project)
    ffmpeg = find_tool("ffmpeg")
    if ext in IMAGE_EXT:
        try:
            im = Image.open(src)
            im.load()
        except Exception as e:
            raise MediaError("this picture could not be opened") from e
        im = im.convert("RGBA") if (im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)) else im.convert("RGB")
        if max(im.size) > MAX_IMAGE:
            im.thumbnail((MAX_IMAGE, MAX_IMAGE))
        out = d / f"{mid}.{'png' if im.mode == 'RGBA' else 'jpg'}"
        im.save(out, **({"quality": 90} if out.suffix == ".jpg" else {}))
        small = im.convert("RGB").copy()
        small.thumbnail((160, 160))
        fx, fy = subject_position(np.asarray(small))
        faces = detect_faces(np.asarray(im.convert("RGB")))
        fx, fy = face_focus(faces, (fx, fy))
        item = MediaItem(id=mid, file=f"media/{out.name}", kind="image", caption=caption, tags=tags or [], width=im.width, height=im.height, fx=fx, fy=fy,
                         faces=faces, source=source, credit=credit, licence=licence)
    else:
        info = probe(src)
        if not info["width"]:
            raise MediaError("no video picture was found in this file")
        out = d / f"{mid}.mp4"
        vf = "fps=30,scale='min(1080,iw)':-2:flags=lanczos,format=yuv420p"
        if ext in GIF_EXT:
            vf = "fps=30,scale='trunc(min(1080,iw)/2)*2':'trunc(ih*min(1080,iw)/iw/2)*2':flags=lanczos,format=yuv420p"
        _run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-movflags", "+faststart", str(out)])
        info = probe(out)
        audio_file = ""
        if ext in VIDEO_EXT and has_audio(src):                                  # the picture file is silent: keep the sound next to it, for layers that want it
            ap = d / f"{mid}.audio.m4a"
            _run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(ap)])
            audio_file = f"media/{ap.name}"
        frame = d / f"_{mid}.png"
        _run([ffmpeg, "-y", "-v", "error", "-ss", str(min(1.0, info["duration"] / 2)), "-i", str(out), "-frames:v", "1", "-vf", "scale=160:-2", str(frame)])
        poster = np.asarray(Image.open(frame).convert("RGB"))
        fx, fy = subject_position(poster)
        faces = detect_faces(poster)
        fx, fy = face_focus(faces, (fx, fy))
        frame.unlink(missing_ok=True)
        item = MediaItem(id=mid, file=f"media/{out.name}", kind="gif" if ext in GIF_EXT else "video", caption=caption, tags=tags or [],
                         width=info["width"], height=info["height"], duration=round(info["duration"], 2), fx=fx, fy=fy, faces=faces, source=source, credit=credit,
                         licence=licence, audio_file=audio_file)
    meta = project.meta()
    meta.media = [m for m in meta.media if m.id != item.id] + [item]
    project.save_meta(meta)
    return item


def remove_media(project, media_id: str) -> bool:
    meta = project.meta()
    keep = [m for m in meta.media if m.id != media_id]
    if len(keep) == len(meta.media):
        return False
    gone = next(m for m in meta.media if m.id == media_id)
    (project.dir / gone.file).unlink(missing_ok=True)
    if gone.audio_file:
        (project.dir / gone.audio_file).unlink(missing_ok=True)
    meta.media = keep
    project.save_meta(meta)
    return True


def composition_media(project) -> dict:
    """What the composition needs to know about each media item (paths are made relative when written next to the page)."""
    out = {}
    for m in project.meta().media:
        if m.kind == "audio":
            continue
        p = project.dir / m.file
        if not p.exists():
            continue
        out[m.id] = {"src": f"media/{p.name}", "kind": "video" if m.kind in ("video", "gif") else "image", "fx": m.fx, "fy": m.fy, "w": m.width, "h": m.height, "role": m.role, "faces": m.faces, "textBand": m.text_band, "shots": m.shots,
                     "trim": 0, "loop": m.role != "a_roll" and (m.kind == "gif" or (m.kind == "video" and m.duration and m.duration < 12)), "_abs": str(p)}
    return out


def speech_envelope(wav: Path, dt: float = 0.04) -> Optional[dict]:
    """Loudness of the voice over time (0-1 every 40 ms): drives mouths and equaliser bars so they move with the real audio."""
    import soundfile as sf

    try:
        x, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    except Exception:
        return None
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = max(1, int(sr * dt))
    n = len(x) // hop
    if n == 0:
        return None
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    ref = float(np.percentile(rms, 95)) or 1.0
    v = np.clip(rms / ref, 0, 1) ** 0.8
    return {"dt": dt, "v": [round(float(a), 2) for a in v]}


def crop_window(item: MediaItem, aspect: str) -> tuple[float, float, float, float]:
    """The part of the picture a 'cover' crop for this aspect shows: (x0, y0, w, h) as fractions, positioned like CSS object-position (fx, fy)."""
    target = {"9:16": 9 / 16, "1:1": 1.0, "16:9": 16 / 9}[aspect]
    cur = item.width / item.height if item.height else 1.0
    if cur > target:
        w = target / cur
        return (item.fx * (1 - w), 0.0, w, 1.0)
    h = cur / target
    return (0.0, item.fy * (1 - h), 1.0, h)


def faces_in_frame(item: MediaItem, aspect: str) -> list[list[float]]:
    """Faces as they appear in the framed picture (fractions of the frame), after the crop; faces cropped out are dropped."""
    x0, y0, cw, ch = crop_window(item, aspect)
    out = []
    for fx, fy, fw, fh in item.faces:
        cx, cy = (fx + fw / 2 - x0) / cw, (fy + fh / 2 - y0) / ch
        if 0 <= cx <= 1 and 0 <= cy <= 1:
            out.append([(fx - x0) / cw, (fy - y0) / ch, fw / cw, fh / ch])
    return out


def text_layout(item: MediaItem, aspect: str) -> str:
    """'lower' puts the scene's text in the lower part of the frame; when people are standing there, 'upper' keeps the text off their faces."""
    low = [f for f in faces_in_frame(item, aspect) if f[1] + f[3] / 2 > 0.52]
    high = [f for f in faces_in_frame(item, aspect) if f[1] + f[3] / 2 <= 0.52]
    return "upper" if low and not high or (low and sum(f[2] * f[3] for f in low) > sum(f[2] * f[3] for f in high)) else "lower"
