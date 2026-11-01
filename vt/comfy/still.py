"""One generated picture, start to finish: a prompt in, a PNG in the project's media bin, with provenance and a cache.

The same prompt, size, seed and workflow version is the same picture, so asking twice never renders twice. Everything the
person should be told (a missing model, a server that is down) comes back as a ComfyError in words.
"""
from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from ..util import now_iso, read_json, write_json
from .client import ComfyClient, ComfyError, output_files
from .workflows import Workflow

PROVENANCE = "comfy_stills.json"


def still_key(workflow: Workflow, prompt: str, aspect: str, seed: int) -> str:
    raw = "|".join([workflow.id, str(workflow.version), prompt.strip(), aspect, str(seed)])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def generate_still(project, client: ComfyClient, workflow: Workflow, prompt: str, *, aspect: str = "9:16", seed: int = 1, caption: str = "",
                   scene: Optional[str] = None, progress: Callable[[float, str], None] = lambda fraction, message: None,
                   cancelled: Callable[[], bool] = lambda: False, timeout: float = 600.0, checked: bool = False):
    """Returns (MediaItem, provenance record). `checked=True` skips the server check when the caller has just made it for a whole batch."""
    from ..director.media import add_media

    if workflow.kind != "image":
        raise ComfyError(f"{workflow.label} makes clips, not pictures.", kind="rejected")
    started = time.time()
    key = still_key(workflow, prompt, aspect, seed)
    log = read_json(project.dir / PROVENANCE, {"stills": []}) or {"stills": []}
    for earlier in log["stills"]:
        if earlier.get("key") == key and any(m.id == earlier["media"] for m in project.meta().media):
            return next(m for m in project.meta().media if m.id == earlier["media"]), earlier
    if not checked:
        problems = workflow.problems(client.object_info())
        if problems:
            raise ComfyError(f"{workflow.label} cannot run on this server: " + "; ".join(problems[:4]), kind="rejected", detail=problems)
    graph, used = workflow.patched(image="", prompt=prompt, aspect=aspect, seconds=0, seed=seed, prefix=f"video_tool/{project.id}")
    progress(0.05, "Queued")
    prompt_id = client.submit(graph)
    entry = client.wait(prompt_id, lambda fraction, message: progress(0.1 + 0.8 * fraction, message), cancelled, timeout)
    files = output_files(entry, workflow.output) or output_files(entry)
    if not files:
        raise ComfyError("ComfyUI finished but produced no picture.", kind="failed", detail=entry.get("outputs"))
    with tempfile.TemporaryDirectory() as work_dir:
        raw = client.download(files[0]["filename"], files[0]["subfolder"], files[0]["type"], Path(work_dir) / f"still_{key}.png")
        item = add_media(project, raw, caption=caption or prompt[:80], tags=["generated", "still"], source="comfyui", licence="generated locally")
    record = {"key": key, "media": item.id, "workflow": workflow.id, "workflow_version": workflow.version, "prompt": prompt, "seed": used["seed"],
              "aspect": aspect, "size": [used["width"], used["height"]], "prompt_id": prompt_id, "scene": scene,
              "seconds_taken": round(time.time() - started, 1), "made_at": now_iso(), "server": client.url}
    log["stills"].append(record)
    write_json(project.dir / PROVENANCE, log)
    progress(1.0, "Done")
    return item, record
