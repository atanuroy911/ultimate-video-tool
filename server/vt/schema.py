"""Data contracts shared by every stage, the planner, the composer, the server and the MCP tools."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .visual_motion import MotionPoint, validate_points, recipe

# --------------------------------------------------------------------------- transcript


class Word(BaseModel):
    id: str
    text: str
    start: float
    end: float
    caption_start: Optional[float] = None
    caption_end: Optional[float] = None
    conf: float = 1.0
    lang: Literal["bn", "en", "other"] = "bn"
    flag: Optional[Literal["review"]] = None
    cut: bool = False
    speaker: Optional[str] = None     # who says it (scripts written as 'Name: text')


class Transcript(BaseModel):
    language: str = "bn"
    words: list[Word] = Field(default_factory=list)

    def by_id(self) -> dict[str, Word]:
        return {w.id: w for w in self.words}

    def kept(self) -> list[Word]:
        return [w for w in self.words if not w.cut]


class Beat(BaseModel):
    id: str
    word_ids: list[str]
    start: float
    end: float
    text: str
    speaker: Optional[str] = None     # who is talking (scripts written as 'Name: text' lines, discussions)


class Beats(BaseModel):
    beats: list[Beat] = Field(default_factory=list)


class Cuts(BaseModel):
    """Kept ranges (source time). `map_time` converts source time -> output time."""

    source_duration: float = 0.0
    keep: list[tuple[float, float]]

    @model_validator(mode="before")
    @classmethod
    def _coerce_duration(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "source_duration" not in data and "source_dur" in data:
                data["source_duration"] = data["source_dur"]
            elif "source_duration" not in data and data.get("keep"):
                data["source_duration"] = max(e for _, e in data["keep"])
        return data

    @property
    def output_duration(self) -> float:
        return sum(e - s for s, e in self.keep)

    def map_time(self, t: float) -> Optional[float]:
        """Source time -> output time, or None if t falls inside a removed region."""
        acc = 0.0
        for s, e in self.keep:
            if s <= t <= e:
                return acc + (t - s)
            acc += e - s
        return None

    def map_time_nearest(self, t: float) -> float:
        """Like map_time but snaps cut-region times to the nearest kept boundary."""
        acc = 0.0
        for s, e in self.keep:
            if t < s:
                return acc
            if t <= e:
                return acc + (t - s)
            acc += e - s
        return acc


# --------------------------------------------------------------------------- elements (components)

STRICT = ConfigDict(extra="forbid")
TitleText = Annotated[str, Field(min_length=1, max_length=40)]

BLENDS = ("normal", "multiply", "screen", "overlay", "darken", "lighten", "soft-light", "difference")


class Transform(BaseModel):
    """Everything an editor can do to one element besides moving, sizing, turning and fading it (plan step E17, human in the loop): stretch, slant, flip, pivot, 3D tilt, a corner-pin
    warp, a crop with rounded corners, blur and a blend. All neutral by default; an element with any of them set is a free element, which no layout rule moves or fits."""
    model_config = STRICT
    stretch_x: float = Field(default=1, ge=.1, le=5, description="Stretch across, on top of size (1 is none)")
    stretch_y: float = Field(default=1, ge=.1, le=5, description="Stretch up and down, on top of size (1 is none)")
    skew_x: float = Field(default=0, ge=-60, le=60, description="Slant sideways, degrees")
    skew_y: float = Field(default=0, ge=-60, le=60, description="Slant up and down, degrees")
    flip_x: bool = Field(default=False, description="Mirror left and right")
    flip_y: bool = Field(default=False, description="Mirror top and bottom")
    pivot_x: float = Field(default=.5, ge=0, le=1, description="What it turns, slants and tilts around: 0 left edge, 1 right edge")
    pivot_y: float = Field(default=.5, ge=0, le=1, description="0 top edge, 1 bottom edge")
    tilt_x: float = Field(default=0, ge=-80, le=80, description="Tilt toward or away from the viewer, degrees (3D)")
    tilt_y: float = Field(default=0, ge=-80, le=80, description="Turn left or right in 3D, degrees")
    warp: Optional[list[list[float]]] = Field(default=None, description="Corner pin: how far each of the four corners moves, [dx, dy] as a fraction of the element's own size, in the order top left, "
                                                                        "top right, bottom right, bottom left")
    crop: Optional[list[float]] = Field(default=None, description="Part of the element cut away, as fractions of its size: [top, right, bottom, left]")
    crop_radius: float = Field(default=0, ge=0, le=1, description="Rounded corners of the crop: 0 square, 1 as round as it can be")
    blur: float = Field(default=0, ge=0, le=60, description="Blur, in pixels of the frame")
    blend: Literal["normal", "multiply", "screen", "overlay", "darken", "lighten", "soft-light", "difference"] = Field(default="normal", description="How it mixes with what is behind it")

    @field_validator("warp")
    @classmethod
    def four_corners(cls, v):
        if v is None:
            return v
        if len(v) != 4 or any(len(c) != 2 or any(not -1 <= n <= 1 for n in c) for c in v):
            raise ValueError("warp is four corners, each [dx, dy] between -1 and 1 (top left, top right, bottom right, bottom left)")
        return v

    @field_validator("crop")
    @classmethod
    def four_sides(cls, v):
        if v is None:
            return v
        if len(v) != 4 or any(not 0 <= n <= .95 for n in v) or v[0] + v[2] > .95 or v[1] + v[3] > .95:
            raise ValueError("crop is [top, right, bottom, left], each between 0 and 0.95, and opposite sides together under 0.95")
        return v

    def is_neutral(self) -> bool:
        return not self.model_dump(exclude_defaults=True)


def has_transform(t: Optional["Transform"]) -> bool:
    """Is anything of it set? An element with something set is free (placed by hand)."""
    return t is not None and not t.is_neutral()


class _El(BaseModel):
    model_config = STRICT
    id: Optional[str] = None
    edited: bool = False
    start: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Exact appearance time in video seconds; overrides the generated word timing")
    end: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Exact disappearance time in video seconds")
    x: Optional[float] = Field(default=None, ge=0, le=1, description="Horizontal centre in the frame, from left to right")
    y: Optional[float] = Field(default=None, ge=0, le=1, description="Vertical centre in the frame, from top to bottom")
    scale: float = Field(default=1, ge=0.05, le=5)
    rotation: float = Field(default=0, ge=-360, le=360)
    opacity: float = Field(default=1, ge=0, le=1)
    transform: Optional[Transform] = Field(default=None, description="Stretch, slant, flip, pivot, 3D tilt, corner-pin warp, crop, blur and blend (all optional)")
    keyframes: list[MotionPoint] = Field(default_factory=list, max_length=100, description="Editable movement points on the video clock, shared by preview and export")
    entrance: str = Field(default="auto", max_length=64, description="auto, none (already in place, no fade), or an entrance id from style.motion_kit")

    @field_validator("entrance")
    @classmethod
    def valid_entrance(cls,value):
        return recipe(value,'entrances')

    @field_validator("keyframes")
    @classmethod
    def ordered_motion(cls, value):
        return validate_points(value)
    at_word: str = Field(description="id of the spoken word at which this element animates in")
    until_word: Optional[str] = Field(default=None, description="id of the spoken word after which it leaves; over a picture it leaves by itself "
                                                                "after its sentence (1.5 to 3 s) so the picture gets the frame back; in a cartoon it leaves "
                                                                "when the next picture arrives unless this word comes later")

    @model_validator(mode="after")
    def valid_range(self):
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("End must be after start")
        return self


class TextLook(BaseModel):
    text_style: Literal["plain", "outline", "neon", "marker", "paint", "chalk", "paper"] = "plain"
    ink: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$", description="Optional lettering colour; empty follows the theme")
    letter_spacing: float = Field(default=0, ge=-.08, le=.3, description="Space between letters in em")


class Title(_El, TextLook):
    """Big heading in the accent colour: the topic or keyword being explained."""

    type: Literal["title"] = "title"
    text: str = Field(min_length=1, max_length=40)


class ValueCard(_El):
    """Tilted card with a big number/price and a small label below it."""

    type: Literal["value_card"] = "value_card"
    value: str = Field(min_length=1, max_length=14, description="e.g. ৳১০০ or 5%")
    label: str = Field(default="", max_length=36)


class BigNumber(_El):
    """One striking statistic, very large, with optional unit and label."""

    type: Literal["big_number"] = "big_number"
    value: str = Field(min_length=1, max_length=12)
    unit: str = Field(default="", max_length=10)
    label: str = Field(default="", max_length=40)


class Arrow(_El):
    """Animated arrow showing cause -> effect or direction of flow."""

    type: Literal["arrow"] = "arrow"
    direction: Literal["down", "up", "left", "right"] = "down"
    label: str = Field(default="", max_length=26)


class IconRow(_El):
    """A row of repeated icons or coins (units, years, people...)."""

    type: Literal["icon_row"] = "icon_row"
    icon: str = Field(default="coin", description="'coin' or a Lucide icon name from the icon list")
    count: int = Field(default=3, ge=1, le=8)
    label: str = Field(default="", max_length=36)
    symbol: Optional[str] = Field(default=None, max_length=3, description="coin symbol, default is the theme currency")


class Tag(_El):
    """Yellow highlighter label for a formula, rule of thumb or key phrase."""

    type: Literal["tag"] = "tag"
    text: str = Field(min_length=1, max_length=28)


class CompareSide(BaseModel):
    model_config = STRICT
    title: str = Field(default="", max_length=20)
    value: str = Field(min_length=1, max_length=12)


class Compare(_El):
    """Two options side by side (A vs B) with an optional verdict tag."""

    type: Literal["compare"] = "compare"
    left: CompareSide
    right: CompareSide
    verdict: str = Field(default="", max_length=30)


class ListEl(_El):
    """2-4 numbered points that appear one after another."""

    type: Literal["list"] = "list"
    items: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(min_length=2, max_length=4)


class EqPart(BaseModel):
    model_config = STRICT
    text: str = Field(min_length=1, max_length=12)
    kind: Optional[Literal["val", "op", "res"]] = Field(default=None, description="val=number box, op=operator, res=result box")


class Equation(_El):
    """A simple equation such as আয় − খরচ = লাভ, built piece by piece."""

    type: Literal["equation"] = "equation"
    parts: list[EqPart] = Field(min_length=2, max_length=7)


class Quote(_El):
    """A statement worth stressing, in large type with an accent bar."""

    type: Literal["quote"] = "quote"
    text: str = Field(min_length=1, max_length=90)
    by: str = Field(default="", max_length=26)


class Bar(BaseModel):
    model_config = STRICT
    label: str = Field(max_length=16)
    value: float = Field(ge=0)
    display: Optional[str] = Field(default=None, max_length=12, description="text shown above the bar, default is the value")


class BarChart(_El):
    """Up to five bars growing from the baseline, for comparing numbers."""

    type: Literal["bar_chart"] = "bar_chart"
    bars: list[Bar] = Field(min_length=2, max_length=5)


class Icon(_El):
    """One large icon in a badge with an optional label."""

    type: Literal["icon"] = "icon"
    name: str = Field(description="Icon id: a Lucide name ('coins'), or 'lucide:coins' / 'tabler:coin'. Use the icon list or search_icons.")
    label: str = Field(default="", max_length=26)


class Keyword(_El, TextLook):
    """The one word the speaker stresses, in huge animated type with an underline sweep, optionally with an icon or sticker above it."""

    type: Literal["keyword"] = "keyword"
    text: str = Field(min_length=1, max_length=30)
    icon: Optional[str] = Field(default=None, description="optional line icon id (see Icon.name)")
    emoji: Optional[str] = Field(default=None, description="optional colour sticker: emoji character or hex code, e.g. '1f4b0'")
    style: Literal["underline", "highlight", "stamp"] = "underline"


class Sticker(_El):
    """A big colour emoji sticker that pops in and gently floats, with an optional label. Great for concrete things (a stone, a house, a coin)."""

    type: Literal["sticker"] = "sticker"
    emoji: str = Field(min_length=1, max_length=40, description="emoji character or hex code, e.g. '1faa8' for the rock emoji")
    label: str = Field(default="", max_length=26)


# ---- phase 2: infographics, cartoons, media ------------------------------------------------------------------------------


class Ring(_El):
    """A percentage as a ring (donut) that fills up, with the number in the middle."""

    type: Literal["ring"] = "ring"
    value: float = Field(ge=0, le=100, description="0-100")
    label: str = Field(default="", max_length=30)
    display: Optional[str] = Field(default=None, max_length=10, description="text in the middle, default is the value with a % sign")


class Point(BaseModel):
    model_config = STRICT
    label: str = Field(default="", max_length=10)
    value: float


class LineChart(_El):
    """A line that draws itself through 3-8 values over time (trend, growth, decline)."""

    type: Literal["line_chart"] = "line_chart"
    points: list[Point] = Field(min_length=3, max_length=8)
    unit: str = Field(default="", max_length=6)
    label: str = Field(default="", max_length=30)


class Step(BaseModel):
    model_config = STRICT
    title: str = Field(min_length=1, max_length=24)
    detail: str = Field(default="", max_length=44)


class Steps(_El):
    """2-5 numbered steps joined by a line that draws itself: a process, how-to or sequence."""

    type: Literal["steps"] = "steps"
    items: list[Step] = Field(min_length=2, max_length=5)


class Event(BaseModel):
    model_config = STRICT
    when: str = Field(min_length=1, max_length=12)
    what: str = Field(min_length=1, max_length=32)


class Timeline(_El):
    """2-5 dated events along a line (years, days, phases)."""

    type: Literal["timeline"] = "timeline"
    events: list[Event] = Field(min_length=2, max_length=5)


class Definition(_El):
    """A term and its meaning on a card: for 'X means Y' sentences."""

    type: Literal["definition"] = "definition"
    term: str = Field(min_length=1, max_length=28)
    meaning: str = Field(min_length=1, max_length=90)


class Checklist(_El):
    """2-5 short items that tick off one after another: recap, requirements, benefits."""

    type: Literal["checklist"] = "checklist"
    items: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(min_length=2, max_length=5)
    title: str = Field(default="", max_length=28)


class ProsCons(_El):
    """Two columns, good points and bad points (or before and after)."""

    type: Literal["pros_cons"] = "pros_cons"
    pros: list[Annotated[str, Field(min_length=1, max_length=30)]] = Field(min_length=1, max_length=3)
    cons: list[Annotated[str, Field(min_length=1, max_length=30)]] = Field(min_length=1, max_length=3)
    pros_title: str = Field(default="", max_length=14)
    cons_title: str = Field(default="", max_length=14)


class Stat(BaseModel):
    model_config = STRICT
    value: str = Field(min_length=1, max_length=10)
    label: str = Field(default="", max_length=20)


class StatRow(_El):
    """2-4 big numbers side by side, each with a small label (results, proof, key figures)."""

    type: Literal["stat_row"] = "stat_row"
    stats: list[Stat] = Field(min_length=2, max_length=4)


class Question(_El):
    """A question card with optional answer choices; the answer is highlighted at the end."""

    type: Literal["question"] = "question"
    text: str = Field(min_length=1, max_length=80)
    options: list[Annotated[str, Field(min_length=1, max_length=28)]] = Field(default_factory=list, max_length=4)
    answer: Optional[int] = Field(default=None, ge=0, le=3, description="index of the correct option")


class Feature(BaseModel):
    model_config = STRICT
    title: str = Field(min_length=1, max_length=22)
    detail: str = Field(default="", max_length=40)
    icon: Optional[str] = Field(default=None, description="line icon id")
    emoji: Optional[str] = Field(default=None, description="colour emoji (hex or character)")


class FeatureGrid(_El):
    """2-4 feature cards, each with a small picture, a title and a line of detail (product features, benefits)."""

    type: Literal["feature_grid"] = "feature_grid"
    items: list[Feature] = Field(min_length=2, max_length=4)


class Cta(_El):
    """End card: a headline, a button-shaped call to action and a small line below."""

    type: Literal["cta"] = "cta"
    headline: str = Field(min_length=1, max_length=40)
    button: str = Field(default="", max_length=24)
    sub: str = Field(default="", max_length=40)


class PriceTag(_El):
    """A price badge with an optional crossed-out old price (offer, discount)."""

    type: Literal["price_tag"] = "price_tag"
    price: str = Field(min_length=1, max_length=12)
    old_price: str = Field(default="", max_length=12)
    label: str = Field(default="", max_length=28)


class Callout(BaseModel):
    model_config = STRICT
    text: str = Field(min_length=1, max_length=24)
    x: float = Field(default=0.5, ge=0, le=1)
    y: float = Field(default=0.5, ge=0, le=1)


class Device(_El):
    """A phone, laptop or browser window showing the user's screenshot/photo/video, with optional callouts pointing at parts of it."""

    type: Literal["device"] = "device"
    offset: float = Field(default=0, ge=0, description="Start within the video file, in seconds")
    kind: Literal["phone", "laptop", "browser"] = "phone"
    media: Optional[str] = Field(default=None, description="media id from the project's media bin; empty shows a neutral placeholder")
    caption: str = Field(default="", max_length=40)
    callouts: list[Callout] = Field(default_factory=list, max_length=3)


class SpeakerCard(_El):
    """A speaker's name and key point, with an avatar that animates while they talk (discussion, interview, podcast)."""

    type: Literal["speaker_card"] = "speaker_card"
    name: str = Field(min_length=1, max_length=20)
    text: str = Field(default="", max_length=90)
    side: Literal["left", "right"] = "left"
    color: int = Field(default=0, ge=0, le=5)


CharacterId = Literal["man", "woman", "boy", "girl", "elder", "old_woman", "worker", "teacher", "doctor", "robot"]
Pose = Literal["stand", "point", "think", "wave", "celebrate", "sad", "shrug", "walk", "sit", "idle", "run", "laugh", "count", "confused", "ride"]
Expression = Literal["neutral", "happy", "sad", "surprised", "angry", "thinking", "laugh", "confused"]
SetId = Literal["plain", "village", "market", "home", "office", "classroom", "street", "nature", "studio", "shop"]


class CastMember(BaseModel):
    model_config = STRICT
    who: CharacterId = Field(default="man", description="elder is an old bald man with glasses; old_woman is an elder woman with a grey bun and glasses; woman and man are other adults")
    pose: Pose = "stand"
    expression: Expression = "neutral"
    x: float = Field(default=0.5, ge=0, le=1, description="horizontal position on the set, 0 left to 1 right")
    y: Optional[float] = Field(default=None, ge=0, le=1, description="height of the feet, 0 top to 1 bottom; empty stands on the floor just above the captions (on a tall frame, about 0.69, and the captions fill 0.71 to 0.79), which is nearly always right")
    arrive: Optional[float] = Field(default=None, ge=0, le=30, description="seconds after the cartoon appears when this character arrives; 0 is already there; empty lets them arrive one after another")
    flip: bool = False
    name: str = Field(default="", max_length=14)
    hair: str = Field(default="", pattern=r"^(?:|#[0-9a-fA-F]{6})$", description="Hair colour as #RRGGBB; empty keeps the automatic look from who and name. Reuse it with the same name in every scene.")
    clothes: str = Field(default="", pattern=r"^(?:|#[0-9a-fA-F]{6})$", description="Clothes colour as #RRGGBB; empty keeps the automatic look from who and name. Reuse it with the same name in every scene.")
    count: int = Field(default=3, ge=1, le=5, description="How many fingers to show in the count pose, from 1 to 5")


class CartoonArtifact(BaseModel):
    model_config = STRICT
    media: str = Field(description="An image in this project's media library, including a generated transparent prop")
    x: float = Field(default=.5, ge=0, le=1)
    y: float = Field(default=.6, ge=0, le=1)
    width: float = Field(default=.2, ge=.02, le=1)
    height: float = Field(default=.25, ge=.02, le=1)
    depth: Literal["behind", "front"] = "front"
    rotation: float = Field(default=0, ge=-180, le=180)


class CartoonLabel(BaseModel):
    model_config = STRICT
    text: str = Field(max_length=90)
    treatment: Literal["sign", "chalk", "paint", "neon"] = "sign"
    x: float = Field(default=.5, ge=0, le=1)
    y: float = Field(default=.2, ge=0, le=1)
    width: float = Field(default=.5, ge=.1, le=.95)
    rotation: float = Field(default=0, ge=-45, le=45)


class CartoonCue(BaseModel):
    model_config = STRICT
    actor: int = Field(default=0, ge=0, le=2)
    start: float = Field(default=0, ge=0)
    end: float = Field(default=1, gt=0)
    pose: Pose = "stand"
    expression: Expression = "neutral"
    count: Optional[int] = Field(default=None, ge=1, le=5, description="How many fingers to show in the count pose; empty keeps this character's count")

    @model_validator(mode="after")
    def forward_time(self):
        if self.end <= self.start:
            raise ValueError("The action must end after it starts")
        return self


class Cartoon(_El):
    """An illustrated scene: a set (village, market, office...) with 1-3 animated characters, optional speech bubble and props."""

    type: Literal["cartoon"] = "cartoon"
    set: SetId = "plain"
    character_style: Literal["classic", "ink", "paper"] = "classic"
    framing: Literal["card", "scene"] = Field(default="card", description="Card inside the layout, or a scene filling the video frame")
    world: Literal["illustrated", "3d"] = Field(default="illustrated", description="Illustrated background or a reusable three-dimensional environment")
    lighting: Literal["day", "sunset", "night"] = "day"
    camera: Literal["still", "push", "pull", "pan"] = "push"
    artifacts: list[CartoonArtifact] = Field(default_factory=list, max_length=12, description="Reusable image props, sized and positioned inside the scene")
    labels: list[CartoonLabel] = Field(default_factory=list, max_length=8, description="Text that belongs in the environment: signs, chalk, painted lettering or neon")
    cues: list[CartoonCue] = Field(default_factory=list, max_length=40, description="Character pose changes in video seconds; editable without writing animation code")
    cast: list[CastMember] = Field(min_length=1, max_length=3)
    bubble: str = Field(default="", max_length=70, description="what the first cast member says")
    speaker: int = Field(default=0, ge=0, le=2, description="index of the cast member whose mouth moves with the voice")
    props: list[str] = Field(default_factory=list, max_length=3, description="colour emoji (hex or character) placed on the set")
    extras: list["StoryItem"] = Field(default_factory=list, max_length=12, description="story-engine items drawn over the scene at their words "
                                                                                     "(counting numbers, icons, a beating heart, a clock...); vt/story/motifs.py")


HEX = r"^#[0-9a-fA-F]{3,8}$"


class StoryCharacter(BaseModel):
    """One Cartoon 2 character, the same in every scene (ScenesFile.story_cast); drawn by server/renderer/story/src/figures.tsx."""

    model_config = STRICT
    name: str = Field(default="", max_length=24)
    skin: str = Field(default="#A0663A", pattern=HEX)
    ear: Optional[str] = Field(default=None, pattern=HEX)
    shirt: str = Field(default="#5F9D7A", pattern=HEX)
    pants: str = Field(default="#2b3150", pattern=HEX)
    hair: str = Field(default="#141010", pattern=HEX)
    bun: bool = False
    orna: Optional[str] = Field(default=None, pattern=HEX, description="scarf colour")
    lungi: Optional[str] = Field(default=None, pattern=HEX, description="long skirt or sari colour")
    glasses: bool = False
    mustache: Optional[str] = Field(default=None, pattern=HEX)
    long: bool = False


class StoryItem(BaseModel):
    """One thing drawn in a Cartoon 2 scene (a character, a bubble, a phone, a counter...). Its own properties are flat, exactly as the story engine
    reads them; vt/story/catalog.py says which exist. Times are absolute video seconds."""

    model_config = ConfigDict(extra="allow")
    type: str
    x: Optional[float] = Field(default=None, ge=-3000, le=3000, description="design units: the stage is 540 wide and 960 tall")
    y: Optional[float] = Field(default=None, ge=-3000, le=3000)
    s: Optional[float] = Field(default=None, ge=0.01, le=20)
    rot: Optional[float] = Field(default=None, ge=-3600, le=3600)
    opacity: Optional[float] = Field(default=None, ge=0, le=1)
    z: Optional[float] = None
    at: Optional[float] = Field(default=None, ge=0)
    until: Optional[float] = Field(default=None, ge=0)
    enter: Optional[str] = None
    exit: Optional[str] = None
    loop: Optional[str] = None
    loopAmp: Optional[float] = Field(default=None, ge=0, le=10)
    move: list[dict] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def known(self):
        from .story import catalog as SC

        if self.type not in SC.ELEMENTS:
            raise ValueError(f"unknown story item '{self.type}' (one of: {', '.join(SC.ELEMENTS)})")
        for key, allowed in (("enter", SC.ENTER), ("exit", SC.EXIT), ("loop", SC.LOOP)):
            v = getattr(self, key)
            if v is not None and v not in allowed:
                raise ValueError(f"{self.type}: {key} '{v}' is not one of {allowed}")
        if self.at is not None and self.until is not None and self.until <= self.at:
            raise ValueError(f"{self.type}: leaves before it appears")
        for m in self.move:
            if not isinstance(m.get("t"), (int, float)):
                raise ValueError(f"{self.type}: every movement point needs a time t")
        return self


class Story(_El):
    """A Cartoon 2 scene: a drawn place and its characters, props and effects, animated to the voice (the story engine). Fills the frame."""

    type: Literal["story"] = "story"
    bg: dict = Field(default_factory=lambda: {"type": "plain"}, description="background: {type, ...options} from vt/story/catalog.py BACKGROUNDS")
    items: list[StoryItem] = Field(default_factory=list, max_length=80)
    tag: str = Field(default="", max_length=24, description="the scene chip at the top (place or time), empty for none")
    push: float = Field(default=0.05, ge=0, le=0.4, description="slow push-in over the scene")
    speak: dict[str, list[list[float]]] = Field(default_factory=dict, description="cast id -> [[from, to] video seconds] when that character talks")

    @field_validator("bg")
    @classmethod
    def known_bg(cls, v):
        from .story import catalog as SC

        if not isinstance(v, dict) or v.get("type") not in SC.BACKGROUNDS:
            raise ValueError(f"unknown story background (one of: {', '.join(SC.BACKGROUNDS)})")
        return v


Cartoon.model_rebuild()          # its extras are story items, defined above


class MediaFrame(_El):
    """The user's photo, GIF or video clip as a framed picture inside the scene."""

    type: Literal["media_frame"] = "media_frame"
    offset: float = Field(default=0, ge=0, description="Start within the video file, in seconds")
    media: str = Field(description="media id from the project's media bin")
    frame: Literal["plain", "rounded", "polaroid", "tv"] = "rounded"
    caption: str = Field(default="", max_length=40)
    motion: Literal["kenburns", "none"] = "kenburns"


# ---- phase 2b: diagrams -------------------------------------------------------------------------------------------------


class FlowNode(BaseModel):
    model_config = STRICT
    text: str = Field(min_length=1, max_length=22)
    kind: Literal["start", "step", "decision", "end"] = "step"


class Flow(_El):
    """A flowchart: 2-5 boxes joined by arrows that draw themselves (a process, a chain of cause and effect, a pipeline)."""

    type: Literal["flow"] = "flow"
    nodes: list[FlowNode] = Field(min_length=2, max_length=5)


class Cycle(_El):
    """3-6 items in a circle joined by arrows, with an optional label in the middle (a loop that repeats)."""

    type: Literal["cycle"] = "cycle"
    items: list[Annotated[str, Field(min_length=1, max_length=16)]] = Field(min_length=3, max_length=6)
    center: str = Field(default="", max_length=20)


class Branch(BaseModel):
    model_config = STRICT
    text: str = Field(min_length=1, max_length=20)
    children: list[Annotated[str, Field(min_length=1, max_length=16)]] = Field(default_factory=list, max_length=3)


class Hierarchy(_El):
    """A tree: one root, 2-4 branches, each with up to 3 leaves (types of something, parts of a whole, an org chart)."""

    type: Literal["hierarchy"] = "hierarchy"
    root: str = Field(min_length=1, max_length=22)
    branches: list[Branch] = Field(min_length=2, max_length=4)


class Venn(_El):
    """Two or three overlapping circles with a label in each and one for the overlap (what is shared, what is different)."""

    type: Literal["venn"] = "venn"
    sets: list[Annotated[str, Field(min_length=1, max_length=16)]] = Field(min_length=2, max_length=3)
    overlap: str = Field(default="", max_length=16)


class FunnelStage(BaseModel):
    model_config = STRICT
    label: str = Field(min_length=1, max_length=20)
    value: str = Field(default="", max_length=10)


class Funnel(_El):
    """3-5 stages that narrow from top to bottom, each with an optional number (conversion, drop-off, filtering)."""

    type: Literal["funnel"] = "funnel"
    stages: list[FunnelStage] = Field(min_length=3, max_length=5)


class Pyramid(_El):
    """3-5 levels from the top (smallest) to the base (widest): a hierarchy of needs, priorities, tiers."""

    type: Literal["pyramid"] = "pyramid"
    levels: list[Annotated[str, Field(min_length=1, max_length=22)]] = Field(min_length=3, max_length=5)


class Matrix(_El):
    """A 2 x 2 grid with a label on each axis and four quadrants (priority matrix, high/low comparisons). `highlight` 0-3 marks one quadrant."""

    type: Literal["matrix"] = "matrix"
    x_label: str = Field(default="", max_length=14)
    y_label: str = Field(default="", max_length=14)
    quadrants: list[Annotated[str, Field(min_length=1, max_length=18)]] = Field(min_length=4, max_length=4, description="top-left, top-right, bottom-left, bottom-right")
    highlight: Optional[int] = Field(default=None, ge=0, le=3)


class Pictogram(_El):
    """'7 out of 10 people': a grid of icons with some filled in. Great for proportions said as 'x in y'."""

    type: Literal["pictogram"] = "pictogram"
    total: int = Field(ge=2, le=20)
    highlighted: int = Field(ge=0, le=20)
    emoji: Optional[str] = Field(default="1f9d1", description="colour emoji (hex or character) used for every figure")
    label: str = Field(default="", max_length=36)


class Gauge(_El):
    """A half-circle dial with a needle (score, risk level, speed): 0-100."""

    type: Literal["gauge"] = "gauge"
    value: float = Field(ge=0, le=100)
    label: str = Field(default="", max_length=30)
    low: str = Field(default="", max_length=10)
    high: str = Field(default="", max_length=10)
    display: Optional[str] = Field(default=None, max_length=10)


class Shape(_El):
    """A simple geometric visual, optionally labelled. Use for grouping or a visual cue, not invented data."""

    type: Literal["shape"] = "shape"
    shape: Literal["rectangle", "circle", "triangle", "line"] = "rectangle"
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    label: str = Field(default="", max_length=48)
    width: float = Field(default=0.65, ge=0.1, le=1.0, description="Width as a fraction of the available scene space")
    rounded: bool = True


Element = Annotated[
    Union[Title, ValueCard, BigNumber, Arrow, IconRow, Tag, Compare, ListEl, Equation, Quote, BarChart, Icon, Keyword, Sticker,
          Ring, LineChart, Steps, Timeline, Definition, Checklist, ProsCons, StatRow, Question, FeatureGrid, Cta, PriceTag, Device,
          SpeakerCard, Cartoon, MediaFrame, Flow, Cycle, Hierarchy, Venn, Funnel, Pyramid, Matrix, Pictogram, Gauge, Shape, Story],
    Field(discriminator="type"),
]

ELEMENT_MODELS = [Title, ValueCard, BigNumber, Arrow, IconRow, Tag, Compare, ListEl, Equation, Quote, BarChart, Icon, Keyword, Sticker,
                  Ring, LineChart, Steps, Timeline, Definition, Checklist, ProsCons, StatRow, Question, FeatureGrid, Cta, PriceTag, Device,
                  SpeakerCard, Cartoon, MediaFrame, Flow, Cycle, Hierarchy, Venn, Funnel, Pyramid, Matrix, Pictogram, Gauge, Shape, Story]

Layout = Literal["stack", "split", "hero", "grid", "side", "lower", "upper"]
Transition = Literal["cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip"]
TRANSITIONS = ["cut", "fade", "slide_up", "slide_left", "zoom", "wipe", "whip"]
LAYOUTS = ["stack", "split", "hero", "grid", "side", "lower", "upper"]


# --------------------------------------------------------------------------- scenes


class SceneCaption(BaseModel):
    model_config = STRICT
    highlight_words: list[str] = Field(default_factory=list, description="word ids shown in the accent pill")
    y: Optional[float] = Field(default=None, ge=0, le=1, description="height of this scene's captions (their bottom edge), 0 top to 1 bottom; empty keeps the video's usual place")


class Scrim(BaseModel):
    """Chosen by the contrast engine so text stays readable on top of a photo or video."""

    model_config = STRICT
    ink: Literal["light", "dark"] = "light"
    kind: Literal["none", "shadow", "gradient", "panel"] = "none"
    strength: float = Field(default=0.0, ge=0, le=1)
    edge: Literal["bottom", "top", "full"] = "bottom"
    ratio: float = Field(default=0.0, description="worst-case contrast ratio reached for the scene's text")


class Backdrop(BaseModel):
    """A photo, GIF or video behind the whole scene."""

    model_config = STRICT
    media: str
    motion: Literal["kenburns", "pan", "none"] = "kenburns"
    fx: float = Field(default=0.5, ge=0, le=1, description="subject position, 0 left to 1 right (the crop and the camera move keep it in frame)")
    fy: float = Field(default=0.5, ge=0, le=1)
    person: Optional[list[str]] = Field(default=None, description="where the person is in the picture, as a coarse 48 x 27 grid of 0/1 characters (vt/people.py): elements are only placed where nobody is")
    offset: Optional[float] = Field(default=None, ge=0, description="where in the media the scene starts, in seconds; set for the A-roll, whose picture is already cut to the edited voice")
    scrim: Scrim = Field(default_factory=Scrim)


class Scene(BaseModel):
    model_config = STRICT
    id: str
    beats: list[str] = Field(default_factory=list, description="Narration beats associated with this scene; a manually split visual scene may have none")
    start: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Exact scene start in video seconds; overrides sentence timing")
    layout: Layout = "stack"
    transition_in: Transition = "fade"
    transition_effect: str = Field(default="auto", max_length=64, description="auto, none, or a transition id from style.motion_kit")
    camera_move: str = Field(default="auto", max_length=64, description="auto, none, or a camera id from style.motion_kit")

    @field_validator("transition_effect", "camera_move")
    @classmethod
    def valid_motion_recipe(cls,value,info):
        return recipe(value,'transitions' if info.field_name=='transition_effect' else 'cameras')
    elements: list[Element] = Field(default_factory=list)
    tone: int = Field(default=0, ge=0, le=5, description="colour tone: rotates the accent colours so neighbouring scenes feel different")
    archetype: Optional[str] = Field(default=None, max_length=24, description="the kind of scene the director chose (informational; used by the Studio's 'show as' switch)")
    role: Optional[str] = Field(default=None, max_length=24, description="what the sentences do in the story (hook, claim, number, step...)")
    backdrop: Optional[Backdrop] = None
    caption: SceneCaption = Field(default_factory=SceneCaption)
    stick: Optional[dict] = Field(default=None, description="stick-figure timeline compiled from a Video Script (set, camera, cast, timed actions); see vt/script/compile.py")
    sfx: list[dict] = Field(default_factory=list, description="sound cues [{at_word, id}] from a Video Script")


class ScenesFile(BaseModel):
    model_config = STRICT
    theme: str = "paper"
    planner: Literal["rules", "llm", "claude", "assistant", "manual"] = "rules"
    scenes: list[Scene]
    story_cast: dict[str, StoryCharacter] = Field(default_factory=dict, description="Cartoon 2 characters by id, shared by every story scene")


# --------------------------------------------------------------------------- theme


class ShadowSpec(BaseModel):
    x: float = 6
    y: float = 6
    color: str = "#1b1b1b"
    blur: float = 0


class ThemeColors(BaseModel):
    bg: str
    bg2: Optional[str] = None
    ink: str
    muted: str
    accent: str
    accent2: str
    card: str
    card_border: str
    caption_bg: str
    caption_ink: str
    highlight_bg: str
    highlight_ink: str
    tag_bg: Optional[str] = None
    tag_ink: Optional[str] = None
    arc: Optional[str] = None


class ThemeFonts(BaseModel):
    headline: list[str]
    body: list[str]
    numeral: Optional[list[str]] = None
    caption: Optional[list[str]] = None
    headline_weight: int = 800


class ThemeShape(BaseModel):
    radius: float = 22
    stroke: float = 4
    shadow: ShadowSpec = Field(default_factory=ShadowSpec)
    card_tilt: float = -3


class ThemeBackground(BaseModel):
    kind: Literal["paper", "flat", "gradient", "grid", "dots", "stripes", "checks", "waves", "rings", "mesh", "aurora"] = "paper"
    grain: float = 0.35
    arcs: bool = True
    pattern: float = 0.5          # strength of dots/stripes/waves/... (0-1)
    animated: bool = False        # slow drifting motion, driven by the timeline so renders stay frame-exact


class ThemeMotion(BaseModel):
    preset: Literal["snappy", "smooth", "bouncy"] = "snappy"


class SafeBottom(BaseModel):
    portrait: int = 420           # px above the bottom in 9:16; phone apps cover the lowest ~20% with their own text and buttons
    landscape: int = 64


class ThemeCaption(BaseModel):
    style: Literal["box", "pill", "underline", "none", "pop", "word", "keyword", "paper"] = "box"     # pop: big outlined words, the spoken one lights up (short-form look); word: one huge word at a time; keyword: small line, the key word grows; paper: serif italic on the picture over a paper-coloured halo (watercolour, print looks)
    reveal: Literal["line", "words"] = "line"
    weight: int = 800
    size: int = 60
    words_per_line: int = 6
    safe_bottom: SafeBottom = Field(default_factory=SafeBottom)


class Theme(BaseModel):
    name: str
    label: str = ""
    color: ThemeColors
    font: ThemeFonts
    shape: ThemeShape = Field(default_factory=ThemeShape)
    background: ThemeBackground = Field(default_factory=ThemeBackground)
    motion: ThemeMotion = Field(default_factory=ThemeMotion)
    caption: ThemeCaption = Field(default_factory=ThemeCaption)
    currency: str = "৳"
    sfx: str = "pop"
    style: str = ""               # Design Studio recipe this theme was made from (informational)
    palette: str = ""
    picture: Literal["emoji", "line"] = "emoji"   # line: drawn styles (blueprint, chalkboard, engraving) show line icons, never colour emoji


# --------------------------------------------------------------------------- project


class Options(BaseModel):
    recording_edit: Literal["auto", "subtitles", "screen"] = "auto"  # preserve a tutorial; captions/graphics use a separate band
    director: str = Field(default="best", max_length=80, description="Who directs this video: best, local, claude-server, or claude@<device>.")
    voice_direction: Literal["off", "auto"] = "auto"   # auto: the director adds delivery notes and sounds (sigh, laugh) for voices that can follow them (vt/voice_direction.py)
    look: Literal["classic", "reel", "story"] = "classic"   # story: Cartoon 2, the story engine (vt/story/)     # reel: one picture drawn for each stretch of speech, in one style (vt/reel/)
    reel_style: Literal["auto", "cartoon", "line-art", "comic", "photo"] = "auto"
    review_script: bool = False       # after the director has planned, open the director's script page (Studio /p/{id}/script) before the editor
    plan_review: Literal["auto", "always", "never"] = "auto"   # show the plan before it is made: auto follows the setting `plan_review` (vt/direction/plan_doc.py)
    end_card: str = Field(default="", max_length=40, description="reel look: a line shown over the last picture (Follow for more, Subscribe); empty = nothing is added (the author's spoken line stays theirs)")
    remove_fillers: bool = True
    remove_retakes: bool = True       # cut false starts and repeated takes, keep the last one (vt/retakes.py)
    target_length: Literal["auto", "keep", "60", "90"] = "auto"     # vt/tighten.py: auto shortens a vertical video over 90 s to about 60 s
    asr_model: str = "bn-medium"
    music: Optional[str] = None
    music_volume: float = 0.10        # linear gain before ducking (0.10 = -20 dB); the editor shows it in dB
    duck: bool = True                 # lower the music while someone speaks (side-chain compression, vt/render/mux.py)
    duck_amount: float = Field(default=0.4, ge=0, le=1)     # 0 = barely, 1 = the music nearly disappears under speech
    duck_release: float = Field(default=0.35, ge=0.05, le=2.0)   # seconds the music takes to come back after a phrase
    target_lufs: float = Field(default=-14.0, ge=-23, le=-9)     # overall loudness of the finished video; -14 is what social platforms play at
    music_fade_in: float = Field(default=1.0, ge=0, le=6)
    music_fade_out: float = Field(default=2.0, ge=0, le=8)
    caption_style: Literal["theme", "auto", "pop", "word", "keyword", "box", "pill", "underline"] = "theme"   # auto: pop for vertical videos, the theme's own style otherwise
    cartoon_template: Literal["illustrated", "classic", "ink", "paper"] = "illustrated"
    motion: Literal["auto", "subtle", "cuts", "off"] = "auto"   # shot recipes from video-shotcraft on every element and scene (vt/compose/motion.py)
    beat_sync: bool = True            # pictures and sound cues land on the music's beat (vt/beatsync.py), only when there is music
    sfx: bool = True
    sfx_level: Literal["off", "subtle", "normal", "rich"] = "normal"
    script_policy: Literal["mixed", "bangla"] = "mixed"
    use_subtitles: Literal["auto", "any", "off"] = "auto"  # imported links: auto = the author's own subtitles (and automatic ones for non-English speech); any = every kind; off = speech recognition
    aroll: Literal["auto", "off"] = "auto"         # a video that is imported keeps the speaker's picture (A-roll) and the plan shows the speaker where nothing better illustrates the words
    sound_events: Literal["auto", "off"] = "auto"  # listen for laughter, applause, music, animals ... (vt/sounds.py): pictures where they happen, captions when nobody speaks
    speakers: Literal["auto", "off"] = "auto"      # detect two different voices in a recording (see vt/stages/speakers.py)
    glossary: dict[str, str] = Field(default_factory=dict)


class MediaItem(BaseModel):
    """A picture, GIF or video the user dropped into the project (or downloaded from a stock site)."""

    model_config = ConfigDict(extra="ignore")
    id: str
    file: str                                   # path relative to the project folder, e.g. media/photo1.jpg
    kind: Literal["image", "video", "gif", "audio"] = "image"
    caption: str = ""
    tags: list[str] = Field(default_factory=list)
    width: int = 0
    height: int = 0
    duration: float = 0.0
    fx: float = 0.5
    fy: float = 0.5
    faces: list[list[float]] = Field(default_factory=list)      # detected faces as [x, y, w, h] fractions of the picture, biggest first
    text_band: Optional[float] = None           # a video with subtitles burned into the picture: where (0-1 from the top) that text starts (vt/aroll.py)
    shots: list[list[float]] = Field(default_factory=list)   # camera shots of a video: [t0, t1, head x, head y, head x at the end] (0-1, -1 when no face): the crop jumps at each cut and pans steadily inside a shot (vt/camerapath.py)
    source: str = "upload"                      # upload | pexels | pixabay | openverse
    credit: str = ""
    licence: str = ""
    role: Literal["asset", "a_roll", "b_roll"] = "asset"   # a_roll: the speaker's own picture, cut to match the edited voice (vt/aroll.py); never offered to the planners as B-roll
    audio_file: str = ""                        # a video's own sound, kept as its own file (the picture file is silent), e.g. media/clip.audio.m4a


UseCase = Literal["auto", "general", "product", "story", "discussion", "education"]


class ProjectMeta(BaseModel):
    id: str
    title: str = ""
    auto_title: bool = False      # the person gave no name: the autopilot replaces this placeholder with the AI-written title
    language: str = "bn"
    aspect: Literal["9:16", "1:1", "16:9"] = "9:16"
    theme: str = "paper"
    pace: Literal["calm", "normal", "fast"] = "normal"
    options: Options = Field(default_factory=Options)
    usecase: UseCase = "auto"
    media: list[MediaItem] = Field(default_factory=list)

    def planner_media(self) -> list["MediaItem"]:
        """The pictures and clips the planners may place: everything except the speaker's own A-roll."""
        return [m for m in self.media if m.role != "a_roll"]

    sounds: list[MediaItem] = Field(default_factory=list)    # audio files for the layers (music, effects, voice-over); never offered to the planners
    origin: Optional[dict] = None                            # imported from a link: {url, title, uploader, license, subtitles}
    source: Literal["recording", "script"] = "recording"     # "script": the voice was made from typed text (see vt/tts.py)
    created_at: str = ""
    status: str = "draft"
    stages: dict[str, dict] = Field(default_factory=dict)
    director: dict[str, Any] = Field(default_factory=dict)  # resolved director, requested choice, time, and any fallback reason

    @field_validator("id")
    @classmethod
    def _safe_id(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", v):
            raise ValueError("project id may only contain letters, digits, '.', '_' and '-'")
        return v


class PlanRequest(BaseModel):
    id: str
    project: str
    kind: Literal["full", "scene"] = "full"
    scene_id: Optional[str] = None
    hint: str = ""
    alternatives: int = 1
    status: Literal["queued", "done", "failed"] = "queued"
    created_at: str = ""
    error: str = ""


# --------------------------------------------------------------------------- validation of a plan


class PlanError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _emoji_known(e: str) -> bool:
    from .visuals.emoji import emoji_key

    return emoji_key(e) is not None


def validate_scenes(sf: ScenesFile, tr: Transcript, beats: Beats, icons: set[str] | None = None, media_ids: set[str] | None = None) -> list[str]:
    """Semantic checks on top of pydantic: ids exist, order, coverage, element count, icons."""
    errs: list[str] = []
    words = tr.by_id()
    beat_by_id = {b.id: b for b in beats.beats}
    expected = [b.id for b in beats.beats]
    seen: list[str] = []
    for sc in sf.scenes:
        if not sc.beats and sc.start is None:
            errs.append(f"scene {sc.id}: a scene without narration needs an explicit start time")
        for bid in sc.beats:
            if bid not in beat_by_id:
                errs.append(f"scene {sc.id}: unknown beat '{bid}'")
        seen.extend(sc.beats)
    if seen != expected:
        missing = [b for b in expected if b not in seen]
        if missing:
            errs.append(f"beats not covered by any scene: {missing}")
        if len(seen) != len(set(seen)):
            errs.append("a beat appears in more than one scene")
        if not missing and seen != expected:
            errs.append("scene beats must follow the original beat order")
    ids = [s.id for s in sf.scenes]
    if len(ids) != len(set(ids)):
        errs.append("scene ids must be unique")

    for sc in sf.scenes:
        word_ids: list[str] = []
        for bid in sc.beats:
            if bid in beat_by_id:
                word_ids.extend(beat_by_id[bid].word_ids)
        wset = set(word_ids)
        for el in sc.elements:
            if el.at_word not in words:
                errs.append(f"scene {sc.id}: element at_word '{el.at_word}' is not a transcript word")
            elif el.at_word not in wset and sc.start is None and el.start is None:
                errs.append(f"scene {sc.id}: at_word '{el.at_word}' is outside this scene's beats")
            if el.until_word is not None:
                if el.until_word not in words:
                    errs.append(f"scene {sc.id}: element until_word '{el.until_word}' is not a transcript word")
                elif el.at_word in words and words[el.until_word].start < words[el.at_word].start:
                    errs.append(f"scene {sc.id}: until_word '{el.until_word}' comes before its at_word")
            if icons is not None:
                names = [el.name] if el.type == "icon" else [el.icon] if el.type in ("icon_row", "keyword") else                     [it.icon for it in el.items] if el.type == "feature_grid" else []
                for nm in names:
                    if nm and nm != "coin" and nm not in icons:
                        errs.append(f"scene {sc.id}: unknown icon '{nm}' (use search_icons, or an id like 'lucide:coins' / 'tabler:coin')")
            em = getattr(el, "emoji", None)
            if em and not _emoji_known(em):
                errs.append(f"scene {sc.id}: unknown emoji '{em}' (use its hex code, e.g. '1f4b0', or search_icons)")
            mid = getattr(el, "media", None) if el.type in ("device", "media_frame") else None
            if mid and media_ids is not None and mid not in media_ids:
                errs.append(f"scene {sc.id}: media '{mid}' is not in the project's media bin")
        if sc.backdrop and media_ids is not None and sc.backdrop.media not in media_ids:
            errs.append(f"scene {sc.id}: backdrop media '{sc.backdrop.media}' is not in the project's media bin")
        for wid in sc.caption.highlight_words:
            if wid not in wset:
                errs.append(f"scene {sc.id}: highlight word '{wid}' is outside this scene")
    return errs
