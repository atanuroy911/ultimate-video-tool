"""The Video Script: one JSON document that every planner (rules, local model, Claude, other APIs) fills in. Times are word ids, never seconds."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from . import catalogue as C

VERSION = "1.0"
STRICT = ConfigDict(extra="forbid", populate_by_name=True)

Kind = Literal["stick", "emoji", "explainer", "infographic", "cartoon", "mixed"]
Verb = Literal[tuple(C.VERBS)]                       # type: ignore[valid-type]
Emotion = Literal[tuple(C.EMOTIONS)]                 # type: ignore[valid-type]
SetName = Literal[tuple(C.SETS)]                     # type: ignore[valid-type]


class Meta(BaseModel):
    model_config = STRICT
    title: str = Field(default="", max_length=80)
    language: str = "en"
    audience: str = Field(default="", max_length=60)
    tone: str = Field(default="", max_length=30)
    aspect: Literal["9:16", "1:1", "16:9"] = "9:16"


class CharStyle(BaseModel):
    model_config = STRICT
    color: str = Field(default="#1f2937", pattern=r"^#[0-9a-fA-F]{6}$")
    head: Literal[tuple(C.HEADS)] = "round"           # type: ignore[valid-type]
    accessory: Literal[tuple(C.ACCESSORIES)] = "none"  # type: ignore[valid-type]
    height: Literal[tuple(C.HEIGHTS)] = "adult"        # type: ignore[valid-type]
    hair: Literal[tuple(C.HAIRS)] = "none"             # type: ignore[valid-type]
    shirt: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="colour of the clothes (the body is drawn thick in this colour)")
    skin: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="colour of the face")


class Character(BaseModel):
    model_config = STRICT
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,15}$")
    rig: Literal[tuple(C.RIGS)] = "stick-basic"       # type: ignore[valid-type]
    role: Literal[tuple(C.ROLES)] = "narrator"        # type: ignore[valid-type]
    name: str = Field(default="", max_length=14)
    style: CharStyle = Field(default_factory=CharStyle)
    kind: Literal[tuple(C.KINDS_OF_CAST)] = "person"   # type: ignore[valid-type]
    emoji: Optional[str] = Field(default=None, max_length=16, description="for kind 'emoji': the sticker that plays this actor, an emoji or its hex code, e.g. '1f98a' (fox)")
    art: Optional[Literal[tuple(C.TOON_CHARACTERS)]] = Field(default=None, description="for kind 'toon': which illustrated character plays this role")  # type: ignore[valid-type]


class SetDef(BaseModel):
    model_config = STRICT
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,15}$")
    kind: SetName = "plain"
    props: list[str] = Field(default_factory=list, max_length=8)
    time: Literal[tuple(C.TIMES)] = "day"              # type: ignore[valid-type]
    weather: Literal[tuple(C.WEATHERS)] = "none"       # type: ignore[valid-type]
    art: Optional[Literal[tuple(C.TOON_SCENES)]] = Field(default=None, description="a painted place for the cartoon style, drawn behind the action")  # type: ignore[valid-type]


class Camera(BaseModel):
    model_config = STRICT
    shot: Literal[tuple(C.SHOTS)] = "medium"          # type: ignore[valid-type]
    move: Literal[tuple(C.MOVES)] = "none"            # type: ignore[valid-type]
    focus: Optional[str] = Field(default=None, max_length=24, description="for move 'zoom_to': a prop or cast id of the scene to push toward")


class Action(BaseModel):
    model_config = STRICT
    at_word: str
    who: str
    do: Verb
    from_: Optional[Literal["left", "right"]] = Field(default=None, alias="from")
    to: Optional[float] = Field(default=None, ge=0, le=1, description="horizontal position on the set, 0 left to 1 right")
    to_side: Optional[Literal["left", "right"]] = None
    side: Optional[Literal["left", "right"]] = None
    target: Optional[str] = Field(default=None, max_length=24)
    bubble: Optional[str] = Field(default=None, max_length=70)
    emotion: Optional[Emotion] = None
    count: Optional[int] = Field(default=None, ge=1, le=5)
    prop: Optional[str] = Field(default=None, max_length=24)
    mark: Optional[Literal[tuple(C.MARKS)]] = None     # type: ignore[valid-type]


class SfxCue(BaseModel):
    model_config = STRICT
    at_word: str
    id: Literal[tuple(C.SFX)] = "pop"                 # type: ignore[valid-type]


class ScriptScene(BaseModel):
    model_config = STRICT
    id: str
    beats: list[str] = Field(min_length=1)
    set: Optional[str] = None
    camera: Camera = Field(default_factory=Camera)
    actions: list[Action] = Field(default_factory=list, max_length=24)
    overlays: list[dict[str, Any]] = Field(default_factory=list, description="on-screen elements from the component catalogue (each has type and at_word)")
    sfx: list[SfxCue] = Field(default_factory=list)
    layout: Literal["stack", "split", "hero", "grid", "side", "lower", "upper"] = "stack"
    transition_in: Literal["cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip"] = "fade"
    tone: int = Field(default=0, ge=0, le=5)
    archetype: Optional[str] = Field(default=None, max_length=24)
    role: Optional[str] = Field(default=None, max_length=24)
    backdrop: Optional[dict[str, Any]] = Field(default=None, description="a picture or video from the project's media bin behind the whole scene: "
                                               "{\"media\": \"<media id>\", \"motion\": \"kenburns\" | \"pan\" | \"none\"}. Leave it out when no media fits. "
                                               "A place (a room, a park; day or night) is not a backdrop: define it in `sets` and name it in this scene's `set`.")
    highlight_words: list[str] = Field(default_factory=list, max_length=3)


class VideoScript(BaseModel):
    model_config = STRICT
    version: str = VERSION
    kind: Kind = "explainer"
    meta: Meta = Field(default_factory=Meta)
    cast: list[Character] = Field(default_factory=list, max_length=8)
    sets: list[SetDef] = Field(default_factory=list, max_length=8)
    scenes: list[ScriptScene]
    planner: Literal["rules", "llm", "claude", "assistant", "manual"] = "llm"
