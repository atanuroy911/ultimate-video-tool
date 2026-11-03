"""Editable scene instructions and observed generation history, shared by Studio and tools."""
from __future__ import annotations

import threading
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..util import read_json, write_json

_locks: dict[str, threading.RLock] = {}


class SceneDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instructions: str = Field(default="", max_length=4000)
    director: Literal["configured", "local", "claude-server"] = "configured"
    director_model: str = Field(default="", max_length=100)
    picture_prompt: str = Field(default="", max_length=300)
    picture_recipe: str = Field(default="", max_length=80)
    video_prompt: str = Field(default="", max_length=600)
    video_workflow: str = Field(default="ltx23_i2v", max_length=80)
    source_image: str = Field(default="", max_length=80)
    voice_engine: str = Field(default="auto", max_length=40)
    voice: str = Field(default="auto", max_length=160)
    narration: str = Field(default="", max_length=600)

    @field_validator("picture_recipe")
    @classmethod
    def picture_choice(cls, value):
        from ..engines.fit import BY_ID
        if value and value not in BY_ID:
            raise ValueError("Unknown picture model")
        return value

    @field_validator("video_workflow")
    @classmethod
    def video_choice(cls, value):
        from ..comfy import list_workflows
        if value not in {w.id for w in list_workflows() if w.kind == "video"}:
            raise ValueError("Unknown video workflow")
        return value

    @field_validator("voice_engine")
    @classmethod
    def voice_choice(cls, value):
        from ..tts import ENGINES
        if value not in {e["id"] for e in ENGINES} | {'auto'}:
            raise ValueError("Unknown voice engine")
        return value


def scene_for(project, sid):
    plan = project.scenes()
    scene = next((s for s in plan.scenes if s.id == sid), None) if plan else None
    if scene is None:
        raise ValueError("This scene no longer exists. Select another scene.")
    return scene


def view(project, sid):
    scene = scene_for(project, sid)
    meta = project.meta()
    saved = (read_json(project.dir / "scene_direction.json", {}) or {}).get(sid, {})
    script = read_json(project.dir / "video_script.json", {}) or {}
    source = next((s for s in script.get("scenes", []) if s.get("id") == sid), None)
    plan = read_json(project.dir / "plan_doc.json", {}) or {}
    moment = next((m for m in plan.get("moments", []) if m.get("id") == sid), None)
    speech = read_json(project.script_path, {}) or {}
    reading = read_json(project.dir / "reel_reading.json", {}) or {}
    notes = [n for n in reading.get("notes", []) if n.get("beat") in scene.beats]
    words = project.transcript().by_id()
    from ..compose.composer import scene_timing
    cuts = project.cuts()
    duration = cuts.output_duration if cuts else max((w.end for w in words.values()), default=1)
    timing = next(t for t in scene_timing(project.scenes(), project.beats(), duration) if t['id']==sid)
    narration = " ".join(w.text for w in words.values() if not w.cut and timing['start'] <= (w.start+w.end)/2 < timing['end'])
    media_ids = {scene.backdrop.media} if scene.backdrop else set()
    media_ids.update(getattr(e, "media", None) for e in scene.elements)
    history = []
    for file, key, kind in [("comfy_stills.json", "stills", "picture"), ("comfy_clips.json", "clips", "video"), ("voice_regenerations.json", "items", "voice")]:
        for record in (read_json(project.dir / file, {}) or {}).get(key, []):
            if record.get("scene") == sid or record.get("media") in media_ids:
                history.append({"kind": kind, **{k: record[k] for k in ("media", "workflow", "model_label", "models", "engine", "voice", "prompt", "seed", "made_at", "source_media") if k in record}})
    image = next((m.id for m in meta.media if m.id in media_ids and m.kind == "image"), "")
    defaults = {"narration": narration[:600], "picture_prompt": next((n["draw"] for n in notes if n.get("draw")), narration[:300]),
                "instructions": (moment or {}).get("why", ""), "source_image": image,
                "voice_engine": speech.get("engine", "auto"), "voice": speech.get("voice", "auto")}
    config = SceneDirection.model_validate({**defaults, **{k:v for k,v in saved.items() if k != "revision"}})
    from ..engines.fit import PICTURES
    from ..comfy import list_workflows
    latest = (read_json(project.dir / "scene_directors.json", {}) or {}).get(sid)
    return {"scene": sid, "revision": saved.get("revision", 0), "direction": config.model_dump(),
            "director": latest or meta.director or {"who": project.scenes().planner}, "source_script": source,
            "source_notes": notes, "source_plan": moment, "components": [e.model_dump(exclude_none=True) for e in scene.elements],
            "history": history, "original_voice": {k:speech[k] for k in ("engine", "voice", "rate") if k in speech},
            "pictures": [{"id": r.id, "label": r.label} for r in PICTURES],
            "videos": [w.public() for w in list_workflows() if w.kind == "video"]}


def save(project, sid, config: SceneDirection, revision: int):
    scene_for(project, sid)
    with _locks.setdefault(str(project.dir), threading.RLock()):
        path = project.dir / "scene_direction.json"
        data = read_json(path, {}) or {}
        if data.get(sid, {}).get("revision", 0) != revision:
            raise ValueError("These instructions changed elsewhere. Reload before saving.")
        data[sid] = {**config.model_dump(), "revision": revision + 1}
        write_json(path, data)
    return view(project, sid)


def propose(project, sid, config: SceneDirection, provider=None):
    """Generate only the selected canonical scene, with the full component vocabulary."""
    import json
    from ..ai import complete_json
    from ..ai.providers import OllamaProvider, ClaudeCLIProvider, current_provider
    from ..planner.catalogue import catalogue_summary, all_icon_names
    from ..schema import Scene, validate_scenes
    current = scene_for(project, sid)
    if provider is None:
        provider = OllamaProvider(config.director_model or None) if config.director == "local" else ClaudeCLIProvider(config.director_model) if config.director == "claude-server" else current_provider()
    words = project.transcript()
    beats = project.beats()
    task = {"instructions":config.instructions,"scene":current.model_dump(exclude_none=True),
            "beats":[b.model_dump() for b in beats.beats if b.id in current.beats],
            "words":[w.model_dump() for w in words.kept()], "capabilities":catalogue_summary(),
            "media":[{"id":m.id,"caption":m.caption,"kind":m.kind} for m in project.meta().media]}
    def check(raw):
        candidate=Scene.model_validate(raw)
        if candidate.id != current.id or candidate.beats != current.beats or candidate.start != current.start:
            return ["Keep the scene id, beats and exact start unchanged."]
        sf=project.scenes().model_copy(update={"scenes":[candidate if s.id==sid else s for s in project.scenes().scenes]})
        return validate_scenes(sf,words,beats,all_icon_names(),{m.id for m in project.meta().media})
    raw=complete_json(json.dumps(task,ensure_ascii=False),Scene.model_json_schema(),provider=provider,model_cls=Scene,check=check,cache=False,
        system="Direct only this scene. Follow the person's instructions. Use the supplied component schemas. Preserve narration anchors and timing. Never invent facts, names, numbers, quotes or media ids. Return the complete Scene JSON.")
    return Scene.model_validate(raw), {"who":provider.name,"model":provider.model()}
