"""Scene direction is available after generation, for every video style."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..direction import editor
from .modules_routes import project_or_404

router = APIRouter(prefix="/api/projects/{pid}/scenes/{sid}/direction", tags=["direction"])


class SaveBody(BaseModel):
    revision: int = Field(ge=0)
    direction: editor.SceneDirection


@router.get("")
def get_direction(pid: str, sid: str):
    try:
        return editor.view(project_or_404(pid), sid)
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.put("")
def save_direction(pid: str, sid: str, body: SaveBody):
    from .app import changed
    try:
        result = editor.save(project_or_404(pid), sid, body.direction, body.revision)
    except ValueError as error:
        raise HTTPException(409, str(error))
    changed(pid)
    return result


@router.post("/rebuild")
def rebuild_scene(pid: str, sid: str):
    from .app import jobs, save_and_compose
    from ..util import read_json, write_json, now_iso
    project=project_or_404(pid)
    info=get_direction(pid,sid)
    config=editor.SceneDirection.model_validate(info["direction"])
    original=editor.scene_for(project,sid).model_dump()
    def work(cb):
        cb("direction",.05,"Directing this scene")
        candidate,record=editor.propose(project,sid,config)
        if editor.scene_for(project,sid).model_dump()!=original:
            raise RuntimeError("The scene changed while the director was working. Your edits were kept; regenerate again when ready.")
        plan=project.scenes()
        save_and_compose(project,plan.model_copy(update={"scenes":[candidate if s.id==sid else s for s in plan.scenes]}))
        log=read_json(project.dir/"scene_directors.json",{}) or {}
        log[sid]={**record,"at":now_iso(),"instructions":config.instructions}
        write_json(project.dir/"scene_directors.json",log)
        return {"scene":sid,"director":record}
    return jobs.submit("scene-direction",pid,"Rebuild this scene",work,when_busy="refuse").public()


@router.post("/voice/undo")
def undo_voice(pid: str,sid: str):
    import threading
    from .app import _audio_lock,_LAYER_LOCKS,changed,jobs
    from ..voice_edit import undo
    if jobs.active_for(pid, ("pipeline", "export", "overdub", "scene-direction", "scene-video", "redraw")):
        raise HTTPException(409,"Wait for generation to finish first.")
    project=project_or_404(pid)
    with _audio_lock(pid),_LAYER_LOCKS.setdefault(pid,threading.Lock()):
        try:
            undo(project,sid)
        except ValueError as error:
            raise HTTPException(409,str(error))
    changed(pid)
    return {"ok":True}


@router.post("/video")
def generate_video(pid: str, sid: str):
    from .app import jobs, changed, compose_all
    from .reel_routes import _set_picture, _remember, _draw_text
    from ..modules.defs import load
    from ..modules.executor import Executor
    project = project_or_404(pid)
    info = get_direction(pid, sid)
    config = info["direction"]
    if not config["video_prompt"].strip():
        raise HTTPException(422, "Describe how this scene should move first.")
    if not any(m.id == config["source_image"] and m.kind == "image" for m in project.meta().media):
        raise HTTPException(422, "Choose a starting picture from this video's media.")
    scene = editor.scene_for(project, sid)
    from .app import get_scenes
    timing = next(t for t in get_scenes(pid)["timing"]["scenes"] if t["id"] == sid)
    if project.meta().aspect == "1:1":
        raise HTTPException(422, "These video models support portrait or landscape. Choose one in Video settings.")
    def work(cb):
        load()
        cb("video", .05, "Generating this scene's motion")
        result = Executor(project.dir).call("gen.video_from_image", {
            "media_id": config["source_image"], "prompt": config["video_prompt"], "workflow": config["video_workflow"],
            "aspect": project.meta().aspect, "seconds": min(8, max(1, timing["end"]-timing["start"])), "scene": sid,
        }, caller="person", why="Regenerate this scene's video", force=True, skip_prerequisites=True)
        if not result.ok:
            raise RuntimeError(result.fix or result.summary)
        media = result.output["media"]["id"]
        current = editor.scene_for(project, sid)
        if current.model_dump()!=scene.model_dump():
            raise RuntimeError("The scene changed during generation. Your edits were kept; the generated video is available in Media.")
        if current.backdrop:
            _remember(project, sid, current.backdrop.media, _draw_text(project, current), None)
        _set_picture(project, sid, media)
        _remember(project, sid, media, config["video_prompt"], None)
        compose_all(project)
        changed(pid)
        return {"media": media}
    return jobs.submit("scene-video", pid, "Regenerate scene video", work, when_busy="refuse").public()
