"""One motion clip, start to finish: still in, silent verified MP4 in the project's media bin, with provenance.

1. check the workflow against the live server (a missing model is named, nothing is queued)
2. upload the still, write the request into the graph, queue it
3. wait (queue position, cancel, timeout), then download the file the output node produced
4. normalise to silent H.264 at the project's frame rate, then prove it: duration, size and a full decode
5. add it to the bin as source "comfyui", role "b_roll", and record where it came from in comfy_clips.json
Regenerating always adds a new item; earlier clips stay until the person deletes them.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from ..util import CREATE_NO_WINDOW, find_tool, now_iso, read_json, write_json
from .client import ComfyClient, ComfyError, output_files
from .workflows import Workflow

PROVENANCE = "comfy_clips.json"
MIN_FRAMES_DECODED = 8


def request_key(workflow: Workflow, image_hash: str, prompt: str, aspect: str, seconds: float, seed: Optional[int]) -> str:
    """The same still + prompt + size + length + seed + workflow version is the same clip: asking twice must not render twice."""
    raw = "|".join([workflow.id, str(workflow.version), image_hash, prompt.strip(), aspect, f"{seconds:.1f}", str(seed)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def crop_box(width: int, height: int, ratio: float, fx: float = 0.5, fy: float = 0.5) -> tuple[int, int, int, int]:
    """The largest window of the picture with the clip's shape (width / height = ratio), placed so the subject at (fx, fy) stays inside:
    left, top, right, bottom. The workflow's own scaler crops from the centre, which cuts off a subject standing at the edge."""
    if width / height > ratio:                       # too wide: keep the full height, choose the stretch of width
        w, h = round(height * ratio), height
    else:                                            # too tall: keep the full width, choose the stretch of height
        w, h = width, round(width / ratio)
    left = min(max(round(fx * width - w / 2), 0), width - w)
    top = min(max(round(fy * height - h / 2), 0), height - h)
    return left, top, left + w, top + h


def frame_still(image: Path, size: tuple[int, int], focus: tuple[float, float], dest: Path) -> Path:
    """The still cropped to the clip's shape around its subject, written to `dest` as a PNG."""
    from PIL import Image

    with Image.open(image) as im:
        im = im.convert("RGB")
        box = crop_box(im.width, im.height, size[0] / size[1], *focus)
        im.crop(box).save(dest)
    return dest


def normalise(src: Path, dest: Path, fps: float) -> dict:
    """Silent H.264 yuv420p with even dimensions, faststart; then decode the whole file to prove it. Returns {duration, width, height, frames}."""
    ffmpeg = find_tool("ffmpeg")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(src), "-an", "-vf", f"fps={fps:g},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-movflags", "+faststart", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 1000:
        raise ComfyError("The generated video could not be converted: " + r.stderr[-200:], kind="error")
    check = subprocess.run([ffmpeg, "-v", "error", "-i", str(dest), "-f", "null", "-"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if check.returncode != 0 or check.stderr.strip():
        raise ComfyError("The generated video does not play to the end: " + check.stderr[-200:], kind="error")
    from ..aroll import video_info

    info = video_info(dest)
    if not info:
        raise ComfyError("The generated file has no picture.", kind="error")
    frames = round(info["duration"] * fps)
    if frames < MIN_FRAMES_DECODED:
        raise ComfyError(f"The generated clip is only {frames} frames long.", kind="error")
    return {"duration": round(info["duration"], 2), "width": info["width"], "height": info["height"], "frames": frames}


def generate_clip(project, client: ComfyClient, workflow: Workflow, image: Path, prompt: str, *, aspect: str = "9:16", seconds: float = 3.0,
                  seed: Optional[int] = None, negative: Optional[str] = None, caption: str = "", scene: Optional[str] = None, source_media: Optional[str] = None,
                  focus: tuple[float, float] = (0.5, 0.5), progress: Callable[[float, str], None] = lambda fraction, message: None,
                  cancelled: Callable[[], bool] = lambda: False, timeout: float = 3600.0):
    """Returns (MediaItem, provenance record). Raises ComfyError for anything the person should be told in words."""
    from ..director.media import add_media

    started = time.time()
    progress(0.02, "Checking ComfyUI")
    problems = workflow.problems(client.object_info())
    if problems:
        raise ComfyError(f"{workflow.label} cannot run on this server: " + "; ".join(problems[:4]), kind="rejected", detail=problems)

    with tempfile.TemporaryDirectory() as work_dir:
        work = Path(work_dir)
        still = frame_still(Path(image), workflow.size_for(aspect), focus, work / "still.png")          # the clip's shape, the subject inside it
        still_hash = hashlib.sha1(still.read_bytes()).hexdigest()
        key = request_key(workflow, still_hash, prompt, aspect, seconds, seed)
        log = read_json(project.dir / PROVENANCE, {"clips": []}) or {"clips": []}
        for earlier in log["clips"]:
            if earlier.get("key") == key and seed is not None and any(m.id == earlier["media"] for m in project.meta().media):
                return next(m for m in project.meta().media if m.id == earlier["media"]), earlier      # the identical request was already made

        progress(0.05, "Sending the picture")
        uploaded = client.upload_image(still, f"vt_{project.id}_{still_hash[:10]}.png")
        graph, used = workflow.patched(image=uploaded, prompt=prompt, aspect=aspect, seconds=seconds, seed=seed, negative=negative, prefix=f"video_tool/{project.id}")
        progress(0.08, "Queued")
        prompt_id = client.submit(graph)
        entry = client.wait(prompt_id, lambda fraction, message: progress(0.1 + 0.8 * fraction, message), cancelled, timeout)
        files = output_files(entry, workflow.output) or output_files(entry)
        if not files:
            raise ComfyError("ComfyUI finished but produced no video file.", kind="failed", detail=entry.get("outputs"))

        progress(0.92, "Downloading the clip")
        raw = client.download(files[0]["filename"], files[0]["subfolder"], files[0]["type"], work / Path(files[0]["filename"]).name)
        progress(0.95, "Checking the clip")
        facts = normalise(raw, work / f"clip_{key}.mp4", used["fps"])
        item = add_media(project, work / f"clip_{key}.mp4", caption=caption or prompt[:80], tags=["generated"], source="comfyui", licence="generated locally")

    meta = project.meta()
    for stored in meta.media:
        if stored.id == item.id:
            stored.role = "b_roll"                          # generated footage is B-roll: never the speaker's own picture
            item = stored
    project.save_meta(meta)
    record = {"key": key, "media": item.id, "workflow": workflow.id, "workflow_version": workflow.version, "prompt": prompt, "negative": negative, "seed": used["seed"],
              "aspect": aspect, "seconds_asked": seconds, "frames": facts["frames"], "fps": used["fps"], "size": [facts["width"], facts["height"]], "prompt_id": prompt_id,
              "source_image": Path(image).name, "source_media": source_media, "focus": [round(focus[0], 3), round(focus[1], 3)], "scene": scene,
              "seconds_taken": round(time.time() - started, 1), "made_at": now_iso(), "server": client.url}
    log["clips"].append(record)
    write_json(project.dir / PROVENANCE, log)
    progress(1.0, "Done")
    return item, record
