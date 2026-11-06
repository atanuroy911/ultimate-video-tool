"""What kind of recording did the person bring? Decides the project mode before anything is made.

    talking_head  a video with a person speaking to camera (podcast, vlog): the speaker stays on screen, framed on the face,
                  and graphics are laid around them
    video         a video without a steady face on camera (screen recording, b-roll): the picture is kept, graphics on top
    audio         a voice recording only (or an mp3 with a cover picture): the whole picture is made from graphics

A few frames spread over the video are checked for faces; a face in most of them means a talking head.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .aroll import video_info
from .util import CREATE_NO_WINDOW, find_tool

FRAMES_TO_CHECK = 6
FACE_SHARE_FOR_TALKING_HEAD = 0.5


def frame_at(path: Path, seconds: float, width: int = 480) -> np.ndarray | None:
    """One RGB frame of the video at a time, scaled to a small width (enough to find a face), or None."""
    command = [find_tool("ffmpeg"), "-v", "error", "-ss", f"{seconds:.2f}", "-i", str(path), "-frames:v", "1",
               "-vf", f"scale={width}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    result = subprocess.run(command, capture_output=True, creationflags=CREATE_NO_WINDOW)
    pixels = result.stdout
    if result.returncode or not pixels:
        return None
    height = len(pixels) // (width * 3)
    if height < 8:
        return None
    return np.frombuffer(pixels[: width * height * 3], np.uint8).reshape(height, width, 3)


def default_recording_edit(info: dict, chosen: str = "auto") -> str:
    """The recording mode a new project starts in. The person's own choice ('subtitles' or 'screen') always stands. 'auto' becomes 'subtitles' for a video that
    shows a picture without a person talking to the camera (a screen recording or tutorial: the viewer needs that picture untouched, with captions), and stays
    'auto' for a talking head or audio, which the normal editing suits."""
    if chosen in ("subtitles", "screen"):
        return chosen
    return "subtitles" if info.get("mode") == "video" and info.get("has_picture") else "auto"


def inspect_source(path: Path) -> dict:
    """The mode of a recording, with what was seen: {mode, has_picture, face_share, duration, width, height}."""
    from .director.media import detect_faces

    info = video_info(path)
    if not info:
        return {"mode": "audio", "has_picture": False, "face_share": 0.0, "duration": None, "width": None, "height": None}
    duration = info["duration"]
    times = [duration * (index + 0.5) / FRAMES_TO_CHECK for index in range(FRAMES_TO_CHECK)]
    frames_with_face = frames_seen = 0
    for seconds in times:
        frame = frame_at(path, seconds)
        if frame is None:
            continue
        frames_seen += 1
        faces = detect_faces(frame, limit=2)
        # a face too small to be the speaker (a crowd in the background) does not count
        if faces and faces[0][2] * faces[0][3] > 0.004:
            frames_with_face += 1
    face_share = frames_with_face / frames_seen if frames_seen else 0.0
    mode = "talking_head" if face_share >= FACE_SHARE_FOR_TALKING_HEAD else "video"
    return {"mode": mode, "has_picture": True, "face_share": round(face_share, 2), "duration": round(duration, 2),
            "width": info["width"], "height": info["height"]}
