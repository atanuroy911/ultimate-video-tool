"""Uniform Slot-to-Fragment fill modules."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..registry import Cost, Example, module
from ..workspace import Workspace


class WordRef(BaseModel):
    id: str = Field(description="Grounded transcript word id.")
    text: str = Field(description="Spoken word text.")
    start: float = Field(ge=0, description="Word start in cut-audio seconds.")
    end: float = Field(ge=0, description="Word end in cut-audio seconds.")


class Impact(BaseModel):
    word_id: str | None = Field(default=None, description="Grounded word id where the picture should change.")
    time: float = Field(ge=0, description="Impact time in cut-audio seconds.")
    kind: str = Field(default="speech", description="Impact kind such as stress, pause, event or goal.")
    strength: float = Field(default=0.5, ge=0, le=1, description="Relative impact strength.")
    why: str = Field(default="", description="Plain grounded reason for the impact.")


class Slot(BaseModel):
    id: str = Field(description="Stable cut-plan slot id.")
    start: float = Field(ge=0, description="Slot start in cut-audio seconds.")
    end: float = Field(gt=0, description="Slot end in cut-audio seconds.")
    words: list[WordRef] = Field(default_factory=list, description="Grounded words spoken in the slot.")
    sentence_id: str | None = Field(default=None, description="Owning sentence beat id when known.")
    impact: Impact = Field(description="Point and reason where the picture should change.")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Aspect, duration, must-show, must-avoid and budget constraints.")

    @model_validator(mode="after")
    def valid_span(self):
        if self.end <= self.start:
            raise ValueError("slot end must be after start")
        if not self.start <= self.impact.time <= self.end:
            raise ValueError("impact time must lie inside the slot")
        return self


class Fragment(BaseModel):
    slot_id: str = Field(description="Slot this fragment fills.")
    items: list[dict[str, Any]] = Field(description="Ordinary editable timeline items, never renderer-private state.")
    assets: list[dict[str, Any]] = Field(default_factory=list, description="Artifact or media references used by the items.")
    confidence: float = Field(default=1.0, ge=0, le=1, description="Confidence that the fragment communicates the slot.")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Module and grounded source provenance.")
    placeholder_for: str | None = Field(default=None, description="Async generation ticket this temporarily represents.")


class SlotIn(BaseModel):
    slot: Slot = Field(description="Audio-first slot that needs a visible fragment.")


class TextCardIn(SlotIn):
    text: str | None = Field(default=None, max_length=120, description="Grounded card text; omitted uses the slot's spoken words.")


class MediaFillIn(SlotIn):
    media_id: str = Field(description="Existing project media id to place in the slot.")


class StillZoomIn(MediaFillIn):
    motion: Literal["zoom_in", "zoom_out", "pan_left", "pan_right"] = Field(default="zoom_in", description="Slow camera move over the still.")


def _fragment(slot: Slot, item: dict[str, Any], module_id: str, *, asset: str | None = None, confidence: float = 1.0) -> Fragment:
    return Fragment(slot_id=slot.id, items=[{"start": slot.start, "end": slot.end, **item}],
                    assets=([{"type": "media", "id": asset}] if asset else []), confidence=confidence,
                    provenance={"module": module_id, "word_ids": [word.id for word in slot.words]})


@module(
    id="fill.placeholder", version=1, summary="Fill a slot with a neutral editable placeholder while another visual is pending.",
    when_to_use="A slot must remain visible while an asynchronous asset is pending.", when_not_to_use="For final export when a grounded visual is available.",
    inputs=SlotIn, outputs=Fragment, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.01),
    effects="none", determinism="pure", grounding=(), fallback=None, fallback_reason="This is itself the safe fallback for fill failures.",
    examples=(Example(inputs={"slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Placing a temporary visual",
    log_line=lambda i, o: f"Placed a neutral placeholder in slot {o.slot_id}.",
)
def placeholder(ws: Workspace, inputs: SlotIn) -> Fragment:
    return _fragment(inputs.slot, {"type": "placeholder", "label": "Visual pending"}, "fill.placeholder", confidence=0.2)


@module(
    id="fill.text_card", version=1, summary="Fill a slot with a grounded spoken phrase on a styled editable card.",
    when_to_use="The spoken phrase itself is the clearest and cheapest visual.", when_not_to_use="A concrete picture communicates the idea better.",
    inputs=TextCardIn, outputs=Fragment, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.03),
    effects="none", determinism="pure", grounding=("text",), fallback="fill.placeholder", fallback_reason="A neutral placeholder remains grounded when no useful words exist.",
    examples=(Example(inputs={"slot": {"id": "sl1", "start": 0, "end": 2, "words": [{"id": "w1", "text": "Gravity", "start": 0, "end": 1}], "impact": {"time": 0.5}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Making a grounded text card",
    log_line=lambda i, o: f"Made a grounded text card for slot {o.slot_id}.",
)
def text_card(ws: Workspace, inputs: TextCardIn) -> Fragment:
    spoken = " ".join(word.text for word in inputs.slot.words).strip()
    text = (inputs.text or spoken).strip()
    if not text or (inputs.text and inputs.text.casefold() not in spoken.casefold()):
        raise ValueError("text card text must appear in the slot's spoken words")
    return _fragment(inputs.slot, {"type": "text_card", "text": text}, "fill.text_card")


def _media(ws: Workspace, media_id: str):
    from ...project import Project
    item = next((item for item in Project(ws.root.name, ws.root.parent).meta().media if item.id == media_id), None)
    if item is None:
        raise ValueError(f"media '{media_id}' is not in the project")
    return item


@module(
    id="fill.user_media", version=1, summary="Fill a slot with one explicit picture or clip from the person's media bin.",
    when_to_use="A supplied asset directly illustrates the spoken slot.", when_not_to_use="Its caption or tags do not match the slot.",
    inputs=MediaFillIn, outputs=Fragment, requires=("project.meta", "media.bin"), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="none", determinism="pure", grounding=(), fallback="fill.text_card", fallback_reason="Grounded speech remains when media is unavailable.",
    examples=(Example(inputs={"media_id": "photo", "slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Placing supplied media",
    log_line=lambda i, o: f"Placed supplied media in slot {o.slot_id}.",
)
def user_media(ws: Workspace, inputs: MediaFillIn) -> Fragment:
    item = _media(ws, inputs.media_id)
    return _fragment(inputs.slot, {"type": "media", "media": item.id, "fit": "cover"}, "fill.user_media", asset=item.id)


@module(
    id="fill.still_zoom", version=1, summary="Fill a slot with a supplied still using a slow editable zoom or pan.",
    when_to_use="A relevant still should remain engaging across a multi-second slot.", when_not_to_use="The media is video or the slot is too brief to perceive motion.",
    inputs=StillZoomIn, outputs=Fragment, requires=("project.meta", "media.bin"), produces=(), cost=Cost("instant", ("cpu",), 0.05),
    effects="none", determinism="pure", grounding=(), fallback="fill.user_media", fallback_reason="The still can remain visible without motion.",
    examples=(Example(inputs={"media_id": "photo", "slot": {"id": "sl1", "start": 0, "end": 3, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Adding motion to a still",
    log_line=lambda i, o: f"Placed a moving still in slot {o.slot_id}.",
)
def still_zoom(ws: Workspace, inputs: StillZoomIn) -> Fragment:
    item = _media(ws, inputs.media_id)
    if item.kind != "image":
        raise ValueError("still zoom needs an image")
    return _fragment(inputs.slot, {"type": "media", "media": item.id, "fit": "cover", "anim": inputs.motion}, "fill.still_zoom", asset=item.id)


@module(
    id="fill.speaker", version=1, summary="Fill a slot with the project's speaker footage, face framing and editable punch-in intent.",
    when_to_use="The speaker should carry a slot where no stronger illustrative visual exists.", when_not_to_use="No approved A-roll media exists.",
    inputs=SlotIn, outputs=Fragment, requires=("project.meta", "media.bin"), produces=(), cost=Cost("fast", ("cpu",), 0.2),
    effects="none", determinism="pure", grounding=(), fallback="fill.text_card", fallback_reason="Grounded spoken text remains when A-roll is absent.",
    examples=(Example(inputs={"slot": {"id": "sl1", "start": 0, "end": 2, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Placing speaker footage",
    log_line=lambda i, o: f"Placed speaker footage in slot {o.slot_id}.",
)
def speaker(ws: Workspace, inputs: SlotIn) -> Fragment:
    from ...project import Project
    media = next((item for item in Project(ws.root.name, ws.root.parent).meta().media if item.role == "a_roll"), None)
    if media is None:
        raise ValueError("the project has no approved A-roll media")
    return _fragment(inputs.slot, {"type": "speaker", "media": media.id, "fit": "cover", "punch_in_at": inputs.slot.impact.time},
                     "fill.speaker", asset=media.id)


class GeneratedClipIn(MediaFillIn):
    prompt: str = Field(min_length=3, max_length=600, description="Grounded visual-motion prompt.")
    workflow: str = Field(default="ltx23_i2v", description="Installed image-to-video workflow id.")
    aspect: Literal["9:16", "16:9"] = Field(default="9:16", description="Generated clip shape.")
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1, description="Optional repeatable sampler seed.")
    url: str | None = Field(default=None, description="Optional ComfyUI URL; omitted uses Settings.")


@module(id="fill.generated_clip", version=1, summary="Generate silent motion from an approved still and return it as an editable slot fragment.",
        when_to_use="A high-impact slot needs novel motion and cheaper grounded fills are insufficient.", when_not_to_use="Speaker, supplied media, stock or still motion communicates the slot.",
        inputs=GeneratedClipIn, outputs=Fragment, requires=("project.meta", "media.bin"), produces=("project.meta", "media.bin", "gen.clips"),
        cost=Cost("heavy", ("comfy", "gpu0", "net"), 300.0), effects="external_api", determinism="external", grounding=("prompt",),
        fallback="fill.placeholder", fallback_reason="A neutral placeholder preserves timing when generation is unavailable.",
        engines=("video.generate",),
        examples=(Example(inputs={"media_id": "still", "prompt": "The spoken apple turns slowly", "slot": {"id": "sl1", "start": 0, "end": 3, "impact": {"time": 1}}}, outputs={"slot_id": "sl1", "items": [], "assets": [], "confidence": 1, "provenance": {}, "placeholder_for": None}),),
        toolboxes=("studio", "full"), plain_name="Generating slot footage", log_line=lambda i, o: f"Generated footage for slot {o.slot_id}.", native_outputs=True, version_outputs=False)
def generated_clip(ws: Workspace, inputs: GeneratedClipIn) -> Fragment:
    from .gen import VideoFromImageIn, video_from_image
    seconds = min(8.0, max(1.0, inputs.slot.end - inputs.slot.start))
    result = video_from_image(ws, VideoFromImageIn(media_id=inputs.media_id, prompt=inputs.prompt,
                                                    workflow=inputs.workflow, aspect=inputs.aspect, seconds=seconds,
                                                    seed=inputs.seed, scene=inputs.slot.sentence_id, url=inputs.url))
    media_id = str(result.media["id"])
    fragment = _fragment(inputs.slot, {"type": "media", "media": media_id, "fit": "cover"},
                         "fill.generated_clip", asset=media_id)
    fragment.provenance["generation"] = result.record
    return fragment
