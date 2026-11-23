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
    said = words[:300].rstrip(" .!?।")                                  # "...need." + ". One subject" read as "need.."
    return f"A clear illustration of: {said}. One subject, simple background, no text." if words else "A clear illustration, one subject, simple background, no text."


PROMPT_RULES = (
    "Each prompt describes one picture that a picture model can draw well. It must be self-contained: say the place, what is visible and how big "
    "it is in the frame, and how any person looks (age, clothes), since the model knows nothing else. Describe only visible things, never an absence "
    "or an idea the eye cannot see. Prefer one clear subject; for a rare pose or action choose a close-up. No writing, letters, numbers or logos in "
    "the picture. Plain English, one to three sentences, under 60 words."
)
PROMPTS_SCHEMA = {
    "type": "object", "required": ["prompts"],
    "properties": {"prompts": {"type": "array", "minItems": 1, "maxItems": MAX_COUNT, "items": {
        "type": "object", "required": ["idea", "prompt"],
        "properties": {"idea": {"type": "string", "maxLength": 60}, "prompt": {"type": "string", "minLength": 10, "maxLength": 600}}}}},
}


def write_prompts(project, scene_id: str, count: int = 4, note: str = "", provider=None) -> list[dict]:
    """G3: `count` different picture prompts for the scene, written by the AI chosen in Settings from what is said there and around it.
    Each is {idea, prompt}; the person edits them before anything is drawn. Raises GenError in plain words when no AI can answer."""
    from .ai.providers import AIUnavailable, complete_json, ensure_ai

    count = max(1, min(MAX_COUNT, int(count)))
    words = scene_words(project, scene_id)
    sf = project.scenes()
    ids = [s.id for s in sf.scenes]
    i = ids.index(scene_id)
    around = lambda j: scene_words(project, ids[j]) if 0 <= j < len(ids) else ""          # noqa: E731
    meta = project.meta()
    ask = (f"A {'Bangla' if meta.language == 'bn' else 'English'} explainer video titled \"{meta.title}\".\n"
           f"Said just before this scene: \"{around(i - 1)[:400]}\"\n"
           f"Said in this scene: \"{words[:800]}\"\n"
           f"Said just after: \"{around(i + 1)[:400]}\"\n"
           + (f"The person adds: \"{note.strip()[:300]}\"\n" if note.strip() else "")
           + f"\nWrite {count} picture prompts for the picture behind this scene. Make them clearly different from each other "
           f"(another subject, another angle or another way to show the same point), each with a short idea name of two to five words.\n{PROMPT_RULES}\n"
           "Answer as JSON: {\"prompts\": [{\"idea\": ..., \"prompt\": ...}]}.")
    try:
        p = provider or ensure_ai()
        got = complete_json(ask, PROMPTS_SCHEMA, provider=p, system="You write prompts for a picture model, for one scene of a video.",
                            max_tokens=1500, timeout=240, temperature=0.8, cache=False)
    except AIUnavailable as e:
        raise GenError(f"No AI could write prompts: {str(e)[:200]} Choose one in Settings > AI, or write the prompt yourself.") from e
    out, seen = [], set()
    for x in got["prompts"]:
        key = x["prompt"].strip().lower()
        if key not in seen:
            seen.add(key)
            out.append({"idea": x["idea"].strip()[:60], "prompt": x["prompt"].strip()[:600]})
    return out[:count]


def generate(project, scene_id: str, prompt: str, *, count: int = 4, recipe: str = "", seed: Optional[int] = None, client=None, prompts: Optional[list[str]] = None,
             progress: Callable[[float, str], None] = lambda f, m: None, cancelled: Callable[[], bool] = lambda: False) -> dict:
    """Draw `count` pictures for the scene, one after another, saving the run after each so the panel shows them as they come."""
    from .comfy import ComfyClient, ComfyError, generate_still, picture_workflow
    from .server.comfy_routes import comfy_url

    prompts = [p.strip()[:600] for p in (prompts or []) if p and len(p.strip()) >= 3][:MAX_COUNT]      # G3: one picture from each of these
    prompt = (prompt or (prompts[0] if prompts else "")).strip()
    if len(prompt) < 3:
        raise GenError("Write what the picture should show.")
    count = len(prompts) if prompts else max(1, min(MAX_COUNT, int(count)))
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
                said = prompts[i] if prompts else prompt[:600]
                item, rec = generate_still(project, client, workflow, said, aspect=project.meta().aspect, seed=first + i, caption=said[:80],
                                           scene=scene_id, checked=i > 0, cancelled=cancelled,
                                           progress=lambda f, m, i=i: progress((i + f) / count, f"Picture {i + 1} of {count}: {m}"))
                run["items"].append({"media": item.id, "seed": rec.get("seed", first + i), "seconds": rec.get("seconds_taken"), **({"prompt": said} if prompts else {})})
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


def clip_models() -> list[dict]:
    """The picture-to-clip workflows there are (G2), for the panel's choice."""
    from .comfy import list_workflows

    return [{"id": w.id, "label": w.label, "sizes": sorted(w.sizes)} for w in list_workflows("video")]


def animate(project, scene_id: str, media_id: str, prompt: str = "", *, workflow: str = "", seconds: float = 3.0, seed: Optional[int] = None, client=None,
            progress: Callable[[float, str], None] = lambda f, m: None, cancelled: Callable[[], bool] = lambda: False) -> dict:
    """G2: one picture made into a short clip (its first frame), kept in the scene's runs as a clip next to the picture it came from."""
    from .comfy import ComfyClient, ComfyError, generate_clip, list_workflows, load_workflow
    from .server.comfy_routes import comfy_url

    scene_words(project, scene_id)
    item = next((m for m in project.meta().media if m.id == media_id), None)
    if item is None or item.kind != "image":
        raise GenError("Choose a picture to make move.")
    seconds = max(1.0, min(8.0, float(seconds)))
    aspect = project.meta().aspect
    own = client is None
    client = client or ComfyClient(comfy_url())
    try:
        try:
            info = client.object_info()
        except ComfyError as e:
            raise GenError(f"No picture engine answered at {getattr(client, 'url', 'its address')}. Start it, or choose one in Settings > Engines.") from e
        if workflow:
            try:
                wf = load_workflow(workflow)
            except KeyError as e:
                raise GenError(f"There is no clip model '{workflow}'.") from e
        else:                                                           # the first clip model the engine can run, else the usual one (it says what is missing)
            ready = [w for w in list_workflows("video") if aspect in w.sizes and not w.problems(info)]
            wf = ready[0] if ready else load_workflow("wan22_i2v")
        if aspect not in wf.sizes:
            raise GenError(f"{wf.label} does not make {aspect} clips.")
        words = (prompt or "").strip() or next((r.get("prompt", "") for r in history(project, scene_id)["runs"]
                                                 if any(i.get("media") == media_id for i in r.get("items", []))), "") or suggest_prompt(project, scene_id)
        run = {"id": uuid.uuid4().hex[:10], "kind": "clip", "prompt": words[:600], "recipe": wf.id, "model": wf.label, "count": 1, "from": media_id,
               "made_at": time.time(), "items": []}
        data = read_json(_file(project, scene_id), {"runs": []}) or {"runs": []}
        data["runs"].append(run)
        _save(project, scene_id, data)
        try:
            clip, rec = generate_clip(project, client, wf, project.dir / item.file, words[:600], aspect=aspect, seconds=seconds, seed=seed,
                                      caption=words[:80], scene=scene_id, source_media=media_id, focus=(item.fx, item.fy), progress=progress, cancelled=cancelled)
            run["items"].append({"media": clip.id, "seed": rec.get("seed", seed or 0), "seconds": rec.get("seconds_taken"), "kind": "clip", "from": media_id})
        except ComfyError as e:
            if getattr(e, "kind", "") != "cancelled":
                run["items"].append({"seed": seed or 0, "error": str(e)[:300], "kind": "clip", "from": media_id})
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
