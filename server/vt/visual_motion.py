"""One editable, absolute video-clock animation contract for all visual tracks."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from functools import lru_cache
import re


@lru_cache(maxsize=1)
def catalogue():
    from . import paths
    source=(paths.RUNTIME/'vt-motion.js').read_text(encoding='utf-8')
    names={'typewriter-moves':'Typewriter','type-rhythm-sync':'Word by word','marker-underline-title':'Draw an underline',
           'card-flip-reveal':'Flip a card','draw-svg-trace':'Draw the outline','paper-title-card':'Paper drop',
           'slam-entrance-moves':'Slam','flying-words':'Flying words','gradient-word-sweep':'Colour sweep'}
    return {kind:[{'id':name,'name':names.get(name,name.replace('-',' ').removesuffix(' moves').capitalize())} for name in re.findall(rf'\b{letter}\["([a-z0-9-]+)"\]\s*=',source)]
            for kind,letter in [('entrances','T'),('transitions','R'),('cameras','S')]}


def recipe(value, kind):
    if value not in ('auto','none') and value not in {r['id'] for r in catalogue()[kind]}:
        raise ValueError(f"Unknown {kind} recipe: {value}")
    return value


class MotionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    time: float = Field(ge=-36000, le=36000, description="Video time in seconds; negative points preserve motion when a trimmed clip moves to the beginning")
    x: float = Field(default=.5, ge=-.5, le=1.5, description="Horizontal centre as a fraction of video width")
    y: float = Field(default=.5, ge=-.5, le=1.5, description="Vertical centre as a fraction of video height")
    scale: float = Field(default=1, ge=.05, le=5, description="Size multiplier")
    rotation: float = Field(default=0, ge=-360, le=360, description="Rotation in degrees")
    opacity: float = Field(default=1, ge=0, le=1, description="Visibility from transparent to solid")
    ease: Literal["linear", "smooth", "in", "out", "hold"] = Field(default="smooth", description="How movement arrives at this point")


def validate_points(points):
    values = TypeAdapter(list[MotionPoint]).validate_python(points)
    if len(values) > 100:
        raise ValueError("Use at most 100 motion points per visual")
    if any(b.time <= a.time for a,b in zip(values, values[1:])):
        raise ValueError("Motion points must have different times, in increasing order")
    return values
