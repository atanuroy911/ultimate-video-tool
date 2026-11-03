"""Project Splitter & Slicer for AI Shorts Highlights.

Takes a parent project (or long-form recording) and materializes a highlight into
a standalone 9:16 child project, with sliced audio, A-roll video cuts, word-timed
transcription re-based to 0-offset, and pipeline-ready scene plan.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .. import gpu, paths
from ..pipeline import Pipeline
from ..project import Project
from ..schema import Cuts, ProjectMeta
from ..util import find_tool, now_iso, read_json, run, slugify, write_json


def _find_source_video(proj: Project) -> Optional[Path]:
    """Check if the project has a video source."""
    for cand in ("input.mp4", "input.mkv", "input.mov", "input.webm", "src.mp4"):
        p = proj.dir / cand
        if p.exists() and p.stat().st_size > 1024:
            return p
    # Check media folder
    aroll = proj.dir / "media" / "aroll.mp4"
    if aroll.exists() and aroll.stat().st_size > 1024:
        return aroll
    return None


def _find_source_audio(proj: Project) -> Path:
    """Find the best quality source audio."""
    if proj.input_audio.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm") and proj.raw_transcript_path.exists():
        return proj.input_audio
    if proj.cut_audio.exists() and proj.cut_audio.stat().st_size > 1024:
        return proj.cut_audio
    if proj.master.exists() and proj.master.stat().st_size > 1024:
        return proj.master
    if proj.input_audio.exists() and proj.input_audio.stat().st_size > 1024:
        return proj.input_audio
    raise FileNotFoundError(f"No audio file found in project {proj.id}")


def slice_short_project(
    parent_pid: str,
    highlight: dict[str, Any],
    index: int = 1,
    run_pipeline: bool = True,
    aroll: str = "auto",
    caption_style: str = "pop",
) -> Project:
    """Slice a highlight segment out of a parent project into a new 9:16 project."""
    parent = Project(parent_pid)
    if not parent.exists():
        raise FileNotFoundError(f"Parent project '{parent_pid}' does not exist")

    parent_meta = parent.meta()
    start_time = max(0.0, float(highlight.get("start_time", 0.0)))
    end_time = float(highlight.get("end_time", start_time + 30.0))
    duration = max(1.0, end_time - start_time)

    title = str(highlight.get("title") or f"Short {index}: {parent_meta.title[:30]}")
    title_slug = slugify(title)[:25] or f"short-{index}"
    prefix = f"{parent_pid[:45]}-s{index}-"
    child_pid = (prefix + title_slug)[:72]

    # Ensure unique project id
    suffix_n = 2
    orig_pid = child_pid
    while (paths.PROJECTS / child_pid).exists():
        child_pid = f"{orig_pid[:72]}-{suffix_n}"
        suffix_n += 1

    child = Project(child_pid)
    child.dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = find_tool("ffmpeg")
    src_audio = _find_source_audio(parent)
    child_audio = child.dir / "input.wav"

    # 1. Slice audio (16kHz mono WAV for Whisper & VT pipeline)
    audio_cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-i", str(src_audio),
        "-ar", "16000", "-ac", "1",
        str(child_audio),
    ]
    run(audio_cmd)

    # 2. Slice source video if present
    src_video = _find_source_video(parent)
    has_video = False
    if src_video:
        child_video = child.dir / "input.mp4"
        use_nvenc = gpu.has_nvenc()
        vcodec = "h264_nvenc" if use_nvenc else "libx264"
        vopts = ["-preset", "p4", "-cq", "22"] if use_nvenc else ["-preset", "fast", "-crf", "22"]

        video_cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start_time:.3f}",
            "-t", f"{duration:.3f}",
            "-i", str(src_video),
            "-c:v", vcodec, *vopts,
            "-c:a", "aac", "-b:a", "192k",
            str(child_video),
        ]
        try:
            run(video_cmd)
            has_video = True
        except Exception:
            # Fallback to pure CPU libx264 copy
            fallback_cmd = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{start_time:.3f}",
                "-t", f"{duration:.3f}",
                "-i", str(src_video),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                str(child_video),
            ]
            try:
                run(fallback_cmd)
                has_video = True
            except Exception:
                has_video = False

    # 3. Use the same transcript clock as the audio chosen above.
    parent_raw_path = parent.transcript_path if src_audio == parent.cut_audio and parent.transcript_path.exists() else parent.raw_transcript_path
    if not parent_raw_path.exists():
        parent_raw_path = parent.transcript_path
    child_words: list[dict] = []
    if parent_raw_path.exists():
        raw_data = read_json(parent_raw_path) or {}
        raw_words = raw_data.get("words", [])
        w_idx = 1
        for w in raw_words:
            w_start = float(w.get("start", 0.0))
            w_end = float(w.get("end", 0.0))
            # Keep words that fall inside [start_time, end_time]
            if w_end > start_time and w_start < end_time:
                s_shifted = max(0.0, round(w_start - start_time, 3))
                e_shifted = max(s_shifted + 0.05, round(w_end - start_time, 3))
                if s_shifted < duration:
                    child_words.append({
                        "id": f"w{w_idx}",
                        "text": w.get("text", ""),
                        "start": s_shifted,
                        "end": min(round(duration, 3), e_shifted),
                        "conf": w.get("conf", 1.0),
                        "lang": w.get("lang", parent_meta.language),
                        "speaker": w.get("speaker"),
                    })
                    w_idx += 1

    write_json(child.raw_transcript_path, {"language": parent_meta.language, "words": child_words})
    write_json(child.transcript_path, {"language": parent_meta.language, "words": child_words})

    # 4. Write initial cuts (full duration kept)
    write_json(child.cuts_path, {"keep": [[0.0, round(duration, 3)]], "source_duration": round(duration, 3)})

    # Copy sliced audio as audio.cut.wav and audio.master.wav so pipeline can skip to words/plan
    shutil.copyfile(child_audio, child.cut_audio)
    shutil.copyfile(child_audio, child.master)

    # 5. Create ProjectMeta
    child_options = dict(parent_meta.options.__dict__ if hasattr(parent_meta.options, "__dict__") else {})
    child_options["aroll"] = aroll if has_video else "off"
    child_options["caption_style"] = caption_style
    child_options["target_length"] = "keep"
    short_origin = {
        "parent_id": parent_pid,
        "parent_title": parent_meta.title,
        "start_time": start_time,
        "end_time": end_time,
        "score": highlight.get("score", 85),
        "hook_sentence": highlight.get("hook_sentence", ""),
        "virality_reason": highlight.get("virality_reason", ""),
    }

    meta = ProjectMeta(
        id=child_pid,
        title=title,
        language=parent_meta.language,
        aspect="9:16",
        theme=parent_meta.theme or "paper",
        pace=parent_meta.pace or "normal",
        created_at=now_iso(),
        options=child_options,
        origin={"short": short_origin},
    )
    child.save_meta(meta)

    # 6. Prepare the child before the job reports success.
    if run_pipeline and child_words:
        pl = Pipeline(child)
        pl.stage_words(force=True)
        pl.stage_context(force=True)
        if has_video and aroll != "off":
            pl.stage_aroll(force=True)
        pl.stage_plan(force=True)
        if has_video and aroll != "off":
            from .. import aroll as AR

            speaker = next((m for m in child.meta().media if m.id == "aroll"), None)
            if speaker is None:
                raise RuntimeError("Could not prepare A-roll video for this Short. Check aroll.error.json in the child project.")
            scenes = child.scenes()
            for scene in scenes.scenes:
                scene.backdrop = None
            AR.apply_speaker(scenes, child, child.beats(), "9:16", speaker, force={scene.id for scene in scenes.scenes})
            if any(scene.backdrop is None or scene.backdrop.media != "aroll" for scene in scenes.scenes):
                raise RuntimeError("The source video could not be placed in every Short scene.")
            child.save_scenes(scenes)
        pl.stage_compose(force=True)

    return child
