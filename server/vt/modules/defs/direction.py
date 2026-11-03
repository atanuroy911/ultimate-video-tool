"""The same editable scene directions exposed in the timeline."""
from typing import Any, Literal
from pydantic import BaseModel, Field
from ..registry import Cost, Example, module
from ..workspace import Workspace
from ...direction.editor import SceneDirection


class DirectionIn(BaseModel):
    scene_id: str = Field(description="Scene id from timeline.get")
    operation: Literal["inspect", "save"] = Field(default="inspect", description="Read provenance and settings, or save the next regeneration instructions")
    revision: int = Field(default=0, ge=0, description="Revision returned by inspect; required for conflict-safe saving")
    direction: SceneDirection | None = Field(default=None, description="Complete scene direction settings when saving")


class DirectionOut(BaseModel):
    view: dict[str, Any] = Field(description="Editable instructions, actual director/model history, component data and generation choices")


@module(id="direct.scene_settings",version=1,summary="Read or change a finished scene's instructions and regeneration models.",
    when_to_use="Inspecting how a scene was made or preparing a scoped image, video, voice or scene regeneration.",
    when_not_to_use="For directly modifying component geometry; use timeline.edit_scene.",
    inputs=DirectionIn,outputs=DirectionOut,requires=("project.meta",),produces=(),
    cost=Cost("instant",("cpu",),.1),effects="writes_artifact",determinism="pure",grounding=(),
    fallback=None,fallback_reason="Existing saved provenance is returned; missing history is never invented.",
    examples=(Example(inputs={"scene_id":"s1"},outputs={"view":{}}),),toolboxes=("autonomous","studio","full"),
    plain_name="Scene direction and model choices",log_line=lambda i,o:f"{i.operation.capitalize()} direction for {i.scene_id}.")
def scene_settings(ws: Workspace, inputs: DirectionIn):
    from ...project import Project
    from ...direction import editor
    project=Project(ws.root.name,ws.root.parent)
    if inputs.operation=="save":
        if inputs.direction is None:
            raise ValueError("Supply the complete direction settings returned by inspect.")
        result=editor.save(project,inputs.scene_id,inputs.direction,inputs.revision)
    else:
        result=editor.view(project,inputs.scene_id)
    return DirectionOut(view=result)
