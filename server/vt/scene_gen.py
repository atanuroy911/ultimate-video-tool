"""Pictures for one scene, made on request (docs/plans/PLAN-SCENE-TOOLS.MD, G1 and G4).

The person (or an agent) asks for N pictures for a scene from a prompt; they are drawn one after another by the picture engine the person chose
(ComfyUI), each lands in the media bin and in the scene's candidates. Every run is kept in `gen/<scene>.json` (prompt, model, seeds, time taken),
so "Redraw" can repeat it with new seeds. Choosing one puts it behind the scene the same way the Director does (a picture scene).
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from .util import read_json, write_json

MAX_COUNT = 8


class GenError(Exception):
    pass


def _file(project, scene_id: str) -> Path:
    if not scene_id or not all(c.isalnum() or c in "-_" for c in scene_id):
        raise GenError(f"'{scene_id}' is not a scene id")
    return project.dir / "gen" / f"{scene_id}.json"


def history(project, scene_id: str) -> dict:
    """The scene's runs, newest first, each with its pictures (media id, seed, seconds) and any picture that failed (with the reason)."""
    data = read_json(_file(project, scene_id), {"runs": []}) or {"runs": []}
    have = {m.id for m in project.meta().media}
    for run in data["runs"]:
        run["items"] = [i for i in run.get("items", []) if i.get("error") or i.get("media") in have]
    data["runs"] = sorted(data["runs"], key=lambda r: r.get("made_at", 0), reverse=True)
    return data


def _save(project, scene_id: str, data: dict) -> None:
    write_json(_file(project, scene_id), data)


def scene_words(project, scene_id: str) -> str:
    """What is said during the scene, for the first prompt."""
    sf = project.scenes()
    sc = next((s for s in (sf.scenes if sf else []) if s.id == scene_id), None)
    if sc is None:
        raise GenError(f"This video has no scene '{scene_id}'.")
    beats = {b.id: b for b in project.beats().beats}
    return " ".join(beats[b].text for b in sc.beats if b in beats).strip()


def suggest_prompt(project, scene_id: str) -> str:
    """A plain first prompt from what is said; the person edits it (G3 adds AI-written prompts)."""
    words = scene_words(project, scene_id)
    return f"A clear illustration of: {words[:300]}. One subject, simple background, no text." if words else "A clear illustration, one subject, simple background, no text."


def generate(project, scene_id: str, prompt: str, *, count: int = 4, recipe: str = "", seed: Optional[int] = None, client=None,
             progress: Callable[[float, str], None] = lambda f, m: None, cancelled: Callable[[], bool] = lambda: False) -> dict:
    """Draw `count` pictures for the scene, one after another, saving the run after each so the panel shows them as they come."""
    from .comfy import ComfyClient, ComfyError, generate_still, picture_workflow
    from .server.comfy_routes import comfy_url

    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        raise GenError("Write what the picture should show.")
    count = max(1, min(MAX_COUNT, int(count)))
    scene_words(project, scene_id)                                       # the scene exists
    own = client is None
    client = client or ComfyClient(comfy_url())
    try:
        try:
            workflow = picture_workflow(recipe, object_info=client.object_info())
        except ComfyError as e:
            raise GenError(f"No picture engine answered at {getattr(client, 'url', 'its address')}. Start it, or choose one in Settings > Engines.") from e
        first = int(seed if seed is not None else (int(time.time()) % 100000) * 10)
        run = {"id": uuid.uuid4().hex[:10], "prompt": prompt[:600], "recipe": recipe, "model": workflow.label, "count": count, "made_at": time.time(), "items": []}
        data = read_json(_file(project, scene_id), {"runs": []}) or {"runs": []}
        data["runs"].append(run)
        _save(project, scene_id, data)
        for i in range(count):
            if cancelled():
                break
            progress(i / count, f"Picture {i + 1} of {count}")
            try:
                item, rec = generate_still(project, client, workflow, prompt[:600], aspect=project.meta().aspect, seed=first + i, caption=prompt[:80],
                                           scene=scene_id, checked=i > 0, cancelled=cancelled,
                                           progress=lambda f, m, i=i: progress((i + f) / count, f"Picture {i + 1} of {count}: {m}"))
                run["items"].append({"media": item.id, "seed": rec.get("seed", first + i), "seconds": rec.get("seconds_taken")})
            except ComfyError as e:
                if getattr(e, "kind", "") == "cancelled":
                    break
                run["items"].append({"seed": first + i, "error": str(e)[:300]})
                if i == 0 and getattr(e, "kind", "") == "rejected":       # the engine cannot run this model at all: the rest would fail the same way
                    _save(project, scene_id, data)
                    raise GenError(str(e)[:300]) from e
            _save(project, scene_id, data)
        progress(1.0, "Done")
        return run
    finally:
        if own:
            client.close()


def forget(project, scene_id: str, media_id: str) -> dict:
    """Take a picture out of the scene's candidates (it stays in the media bin)."""
    data = read_json(_file(project, scene_id), {"runs": []}) or {"runs": []}
    for run in data["runs"]:
        run["items"] = [i for i in run.get("items", []) if i.get("media") != media_id]
    data["runs"] = [r for r in data["runs"] if r.get("items")]
    _save(project, scene_id, data)
    return history(project, scene_id)
