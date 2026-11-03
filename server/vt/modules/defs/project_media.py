"""Thin project-media and theme adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


def _project(ws: Workspace):
    from ...project import Project

    return Project(ws.root.name, ws.root.parent)


class AddMediaIn(BaseModel):
    file: str = Field(description="Absolute or current-working-directory path to an image or video file.")
    caption: str = Field(default="", description="Grounded description supplied by the person.")
    tags: list[str] = Field(default_factory=list, description="Optional search tags supplied by the person.")
    source: str = Field(default="upload", description="Media provenance label, such as upload or stock.")
    credit: str = Field(default="", description="Creator credit when required.")
    licence: str = Field(default="", description="Licence name or URL when known.")


class MediaOut(BaseModel):
    item: dict[str, Any] = Field(description="Validated media-bin item written to the project.")


@module(
    id="project.add_media", version=1, summary="Add and normalize a person's image or video in the project media bin.",
    when_to_use="The person supplied a picture or clip for this video.", when_not_to_use="For audio-only sound assets.",
    inputs=AddMediaIn, outputs=MediaOut, requires=("project.meta",), produces=("project.meta", "media.bin"),
    cost=Cost("slow", ("cpu",), 15.0), effects="writes_artifact", determinism="pure", grounding=("caption",),
    fallback=None, fallback_reason="The existing media importer validates and normalizes the file.",
    examples=(Example(inputs={"file": "photo.png", "caption": "The supplied product photo"}, outputs={"item": {"id": "photo"}}),),
    toolboxes=("studio", "full"), plain_name="Adding media to the project",
    log_line=lambda i, o: f"Added {o.item.get('kind', 'media')} {o.item.get('id', '')} to the project.",
    native_outputs=True, version_outputs=False,
)
def add_media(ws: Workspace, inputs: AddMediaIn) -> MediaOut:
    from ...director.media import add_media as add

    item = add(_project(ws), Path(inputs.file).expanduser(), caption=inputs.caption, tags=inputs.tags,
               source=inputs.source, credit=inputs.credit, licence=inputs.licence)
    return MediaOut(item=item.model_dump(mode="json"))


class RemoveMediaIn(BaseModel):
    media_id: str = Field(description="Stable id of the media-bin item to remove.")


class RemoveMediaOut(BaseModel):
    removed: bool = Field(description="Whether the requested media item existed and was removed.")


@module(
    id="project.remove_media", version=1, summary="Remove one image or video from the project media bin.",
    when_to_use="The person or director no longer wants a media-bin item.", when_not_to_use="For source footage or sound assets.",
    inputs=RemoveMediaIn, outputs=RemoveMediaOut, requires=("project.meta",), produces=("project.meta", "media.bin"),
    cost=Cost("fast", ("cpu",), 1.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="A missing id is reported as not removed.",
    examples=(Example(inputs={"media_id": "photo"}, outputs={"removed": True}),), toolboxes=("studio", "full"),
    plain_name="Removing project media", log_line=lambda i, o: f"{'Removed' if o.removed else 'Did not find'} {i.media_id}.",
    native_outputs=True, version_outputs=False,
)
def remove_media(ws: Workspace, inputs: RemoveMediaIn) -> RemoveMediaOut:
    from ...director.media import remove_media as remove

    return RemoveMediaOut(removed=remove(_project(ws), inputs.media_id))


class AddSoundIn(BaseModel):
    file: str = Field(description="Absolute or current-working-directory path to an audio file.")
    caption: str = Field(default="", description="Plain description of the sound.")
    source: str = Field(default="upload", description="Sound provenance label.")
    credit: str = Field(default="", description="Creator credit when required.")
    licence: str = Field(default="", description="Licence name or URL when known.")


@module(
    id="project.add_sound", version=1, summary="Add and normalize a person's sound file in the project media bin.",
    when_to_use="A supplied sound should become music or an editable audio layer.", when_not_to_use="For the spoken source recording.",
    inputs=AddSoundIn, outputs=MediaOut, requires=("project.meta",), produces=("project.meta", "media.bin"),
    cost=Cost("slow", ("cpu",), 10.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The existing sound importer validates and normalizes the file.",
    examples=(Example(inputs={"file": "music.wav", "caption": "Supplied music"}, outputs={"item": {"id": "music"}}),),
    toolboxes=("studio", "full"), plain_name="Adding sound to the project",
    log_line=lambda i, o: f"Added sound {o.item.get('id', '')} to the project.", native_outputs=True, version_outputs=False,
)
def add_sound(ws: Workspace, inputs: AddSoundIn) -> MediaOut:
    from ...director.media import add_sound as add

    item = add(_project(ws), Path(inputs.file).expanduser(), caption=inputs.caption, source=inputs.source,
               credit=inputs.credit, licence=inputs.licence)
    return MediaOut(item=item.model_dump(mode="json"))


class LoadThemeIn(BaseModel):
    name: str = Field(description="Built-in or project theme name.")


class ThemeOut(BaseModel):
    theme: dict[str, Any] = Field(description="Complete validated theme used by the composer.")


@module(
    id="project.load_theme", version=1, summary="Load a built-in or saved project theme by name.",
    when_to_use="Inspecting the exact colours, type and motion before composition.", when_not_to_use="To create a new style/palette combination.",
    inputs=LoadThemeIn, outputs=ThemeOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.02),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="Unknown names fall back inside the existing theme loader.",
    examples=(Example(inputs={"name": "paper"}, outputs={"theme": {"name": "paper"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Loading the visual theme",
    log_line=lambda i, o: f"Loaded the {o.theme.get('name', i.name)} theme.",
)
def load_theme(ws: Workspace, inputs: LoadThemeIn) -> ThemeOut:
    from ...project import load_theme as load

    return ThemeOut(theme=load(inputs.name).model_dump(mode="json"))


class BuildThemeIn(BaseModel):
    style: str = Field(description="Registered layout and motion style name.")
    palette: str = Field(description="Registered readable colour palette name.")
    name: str | None = Field(default=None, description="Optional name for the generated theme.")
    overrides: dict[str, Any] = Field(default_factory=dict, description="Optional validated theme-field overrides.")


@module(
    id="design.build_theme", version=1, summary="Build a readable theme from an existing style and colour palette.",
    when_to_use="A direction specifies a style and palette combination.", when_not_to_use="A named theme already fits.",
    inputs=BuildThemeIn, outputs=ThemeOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.03),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="The theme builder validates names and contrast.",
    examples=(Example(inputs={"style": "clean", "palette": "sky"}, outputs={"theme": {"name": "clean-sky"}}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Building the visual theme",
    log_line=lambda i, o: f"Built the {o.theme.get('name', 'custom')} theme.",
)
def build_theme(ws: Workspace, inputs: BuildThemeIn) -> ThemeOut:
    from ...designer import build_theme as build

    return ThemeOut(theme=build(inputs.style, inputs.palette, inputs.name, inputs.overrides).model_dump(mode="json"))
