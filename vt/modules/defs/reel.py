"""The reel director's stages as modules the director can call one by one (docs/plans/PLAN-REEL-DIRECTOR.MD section 2): read the script, set one look, make slots, draw one picture."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class ReadIn(BaseModel):
    use_ai: bool = Field(default=True, description="Ask the language AI first; false uses the rules only (no server needed).")


class ReadOut(BaseModel):
    kind: str = Field(description="steps, story, explanation, argument, list or opinion.")
    style: str = Field(description="cartoon, line-art, comic or photo.")
    hook: dict[str, Any] = Field(description="The opening line, its type and strength from 0 to 1.")
    source: str = Field(description="'ai' or 'rules': what did the reading.")
    sentences: int = Field(description="How many sentences got a note.")
    warnings: list[str] = Field(description="Anything the reading had to repair.")


@module(
    id="understand.read_script", version=1, summary="Read the spoken script like a director: its kind, the hook, what each sentence should show, the turns and the look.",
    when_to_use="Before choosing pictures, pace or captions for a reel.", when_not_to_use="For a recording whose picture is the speaker.",
    inputs=ReadIn, outputs=ReadOut, requires=("transcript", "beats"), produces=("reel.reading",),
    cost=Cost("slow", ("ollama",), 40.0), effects="writes_artifact", determinism="external", grounding=("sentence",),
    fallback=None, fallback_reason="Without a language AI the reading falls back to rules over the same sentences.",
    examples=(Example(inputs={"use_ai": False}, outputs={"kind": "steps", "style": "cartoon", "hook": {}, "source": "rules", "sentences": 9, "warnings": []}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reading the script", native_outputs=True,
    log_line=lambda i, o: f"Read {o.sentences} sentences as {o.kind}, drawn as {o.style} ({o.source}).",
)
def read_script_module(ws: Workspace, inputs: ReadIn) -> ReadOut:
    from ...project import Project
    from ...reel.plan import READING
    from ...reel.reading import read_script
    from ...util import write_json

    project = Project(ws.root.name, ws.root.parent)
    reading = read_script(project.beats().beats, use_ai=inputs.use_ai)
    write_json(project.dir / READING, reading.model_dump())
    return ReadOut(kind=reading.kind, style=reading.style, hook=reading.hook.model_dump(), source=reading.source, sentences=len(reading.notes), warnings=reading.warnings)


class SlotsIn(BaseModel):
    pass


class SlotsOut(BaseModel):
    slots: list[dict[str, Any]] = Field(description="Per slot: id, the sentence ids, words, seconds and the chapter card text if any.")
    longest_seconds: float = Field(description="The longest a single picture will stay.")


@module(
    id="cut.reel_slots", version=1, summary="Group the sentences into picture slots from the content; nothing holds a picture over 3 seconds.",
    when_to_use="After the script is read and before drawing.", when_not_to_use="For an A-roll recording.",
    inputs=SlotsIn, outputs=SlotsOut, requires=("beats", "reel.reading"), produces=(), cost=Cost("instant", ("cpu",), 0.1), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="The grouping is arithmetic over the reading and the sentence times.",
    examples=(Example(inputs={}, outputs={"slots": [], "longest_seconds": 2.9}),), toolboxes=("autonomous", "studio", "full"), plain_name="Planning the pictures",
    log_line=lambda i, o: f"Planned {len(o.slots)} pictures, none longer than {o.longest_seconds:.1f} s.",
)
def reel_slots(ws: Workspace, inputs: SlotsIn) -> SlotsOut:
    from ...project import Project
    from ...reel.plan import READING
    from ...reel.reading import Reading
    from ...reel.slots import build_slots
    from ...util import read_json

    project = Project(ws.root.name, ws.root.parent)
    reading = Reading.model_validate(read_json(project.dir / READING, {}))
    slots = build_slots(project.beats().beats, reading)
    return SlotsOut(slots=[{"id": s.id, "beats": [b.id for b in s.beats], "words": s.words, "seconds": round(s.seconds, 2), "card": s.card} for s in slots],
                    longest_seconds=round(max((s.seconds for s in slots), default=0.0), 2))


class StyleIn(BaseModel):
    style: Literal["auto", "cartoon", "line-art", "comic", "photo"] = Field(description="The one look every picture of the video shares; auto lets the reading choose.")


class StyleOut(BaseModel):
    style: str = Field(description="The style now set on the project.")


@module(
    id="direct.set_style", version=1, summary="Choose the one drawing style every picture of the reel shares.",
    when_to_use="The person or the director wants a different look before drawing again.", when_not_to_use="Mid-video: change it for the whole video, not one picture.",
    inputs=StyleIn, outputs=StyleOut, requires=("project.meta",), produces=("project.meta",), cost=Cost("instant", ("cpu",), 0.1), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="A setting change needs no model.",
    examples=(Example(inputs={"style": "line-art"}, outputs={"style": "line-art"}),), toolboxes=("autonomous", "studio", "full"), plain_name="Choosing the look", native_outputs=True, version_outputs=False,
    log_line=lambda i, o: f"The video will be drawn as {o.style}.",
)
def set_style(ws: Workspace, inputs: StyleIn) -> StyleOut:
    from ...project import Project

    project = Project(ws.root.name, ws.root.parent)
    meta = project.meta()
    project.update_meta(options=meta.options.model_copy(update={"reel_style": inputs.style}))
    return StyleOut(style=inputs.style)


class StillIn(BaseModel):
    draw: str = Field(min_length=3, max_length=300, description="What the picture shows, in plain words, using only what the sentence says.")
    scene: str | None = Field(default=None, description="The scene id the picture is for.")
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1, description="A new seed draws the same idea differently.")
    url: str | None = Field(default=None, description="Optional ComfyUI address for this call; omitted uses the connected engine.")


class StillOut(BaseModel):
    media: dict[str, Any] = Field(description="The new media-bin picture.")
    record: dict[str, Any] = Field(description="Workflow, prompt, seed, timing and server.")


@module(
    id="fill.generated_still", version=1, summary="Draw one picture for a sentence in the video's style, on the picture server.",
    when_to_use="A slot needs a picture that does not exist yet, or the person wants another try.", when_not_to_use="Stock, the speaker's own footage or a card says it more cheaply.",
    inputs=StillIn, outputs=StillOut, requires=("project.meta", "media.bin"), produces=("project.meta", "media.bin"),
    cost=Cost("slow", ("comfy", "gpu0", "net"), 20.0), effects="external_api", determinism="external", grounding=("draw",),
    fallback="fill.text_card", fallback_reason="A text card with the key word keeps the timing when no picture server answers.", engines=("image.generate",),
    examples=(Example(inputs={"draw": "a man hands over a check", "scene": "s1"}, outputs={"media": {"id": "m1"}, "record": {}}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Drawing a picture", native_outputs=True, version_outputs=False,
    log_line=lambda i, o: f"Drew picture {o.media.get('id', '')} ({o.record.get('seconds_taken', '?')} s).",
)
def generated_still(ws: Workspace, inputs: StillIn) -> StillOut:
    import hashlib

    from ...comfy import ComfyClient, generate_still, picture_workflow
    from ...project import Project
    from ...reel.style import FIGURE, STYLES, drawing_style, prompt_for
    from ...util import read_json
    from .gen import _url

    project = Project(ws.root.name, ws.root.parent)
    meta = project.meta()
    reading = read_json(project.dir / "reel_reading.json", {}) or {}
    style = drawing_style(meta.options.reel_style if meta.options.reel_style in STYLES else reading.get("style", "cartoon"), meta.theme)
    prompt = prompt_for(inputs.draw, style, reading.get("character") or FIGURE.get(style, ""))
    seed = inputs.seed if inputs.seed is not None else int(hashlib.sha1(f"{project.id}:{inputs.scene}:{prompt}".encode()).hexdigest()[:7], 16)
    client = ComfyClient(_url(inputs.url))
    try:
        item, record = generate_still(project, client, picture_workflow(), prompt, aspect=meta.aspect, seed=seed, caption=inputs.draw[:80], scene=inputs.scene)
    finally:
        client.close()
    return StillOut(media=item.model_dump(mode="json"), record=record)


class HookIn(BaseModel):
    use_ai: bool = Field(default=True, description="Also ask the language AI for a sharper first line; its line is kept only if it adds no fact.")


class HookOut(BaseModel):
    weak: bool = Field(description="Whether the first line is a weak opening.")
    proposals: list[dict[str, Any]] = Field(description="Up to two openings: id, why, kind (trim, reorder, rewrite) and the whole script with that change. Never applied automatically.")


@module(
    id="direct.improve_hook", version=1, summary="When the first line is weak, propose up to two better openings that add no fact; nothing is applied by itself.",
    when_to_use="The script starts with a greeting or a slow lead-in.", when_not_to_use="The first line already asks, warns or surprises.",
    inputs=HookIn, outputs=HookOut, requires=("script.text",), produces=(), cost=Cost("fast", ("ollama",), 8.0), effects="none", determinism="external", grounding=("script",),
    fallback=None, fallback_reason="The rules only trim or move the author's own sentences.",
    examples=(Example(inputs={"use_ai": False}, outputs={"weak": True, "proposals": []}),), toolboxes=("autonomous", "studio", "full"), plain_name="Looking for a stronger opening",
    log_line=lambda i, o: ("The opening is already strong." if not o.weak else f"Found {len(o.proposals)} stronger opening(s) to choose from."),
)
def improve_hook(ws: Workspace, inputs: HookIn) -> HookOut:
    from ...reel import hook as H

    text = str(ws.read_json("script.text").get("text", ""))
    weak = H.is_weak(text)
    return HookOut(weak=weak, proposals=H.propose(text, ai_rewrites=H.ai_first_lines(text) if inputs.use_ai and weak else None) if weak else [])
