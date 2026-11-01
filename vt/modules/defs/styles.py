"""Film styles for directors (vt/styles.py): pick a look by topic or use, then read its style bible while directing."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class ListIn(BaseModel):
    category: str = Field("", description="a style category (e.g. 'Graphic & Type'); empty = all")
    use: str = Field("", description="what the video is for (e.g. 'finance', 'product launch', 'history'); empty = all")


class ListOut(BaseModel):
    styles: list[dict[str, Any]] = Field(description="slug, name, category, uses, one-line summary and the theme to set.")


@module(
    id="style.list", version=1, summary="List the 66 film styles (blueprint, risograph, ink wash, newsreel...) with what each suits.",
    when_to_use="Choosing a look for a video before directing it.", when_not_to_use="Once a style is chosen (use style.get).",
    inputs=ListIn, outputs=ListOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 0.01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Static data.",
    examples=(Example(inputs={"use": "finance"}, outputs={"styles": [{"slug": "briefing-board"}]}),), toolboxes=("autonomous", "studio", "full"),
    plain_name="Looking through the film styles", log_line=lambda i, o: f"Found {len(o.styles)} style(s).",
)
def style_list(ws: Workspace, inputs: ListIn) -> ListOut:
    from ... import styles

    return ListOut(styles=styles.listing(inputs.category, inputs.use))


class GetIn(BaseModel):
    slug: str = Field(description="the style's slug, from style.list")


class GetOut(BaseModel):
    style: dict[str, Any] = Field(description="The style bible: essence, materials, colour, type, motion, camera, sound, native moves, pitfalls.")
    brief: str = Field(description="The same, condensed into director instructions.")


@module(
    id="style.get", version=1, summary="Read one film style's bible: what it is, how it moves, its native moves and its traps.",
    when_to_use="After choosing a style and before planning scenes; set the project's theme to 'style-<slug>'.",
    when_not_to_use="To list styles (use style.list).",
    inputs=GetIn, outputs=GetOut, requires=(), produces=(),
    cost=Cost("fast", ("cpu",), 0.01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Static data.",
    examples=(Example(inputs={"slug": "blueprint"}, outputs={"style": {"slug": "blueprint"}, "brief": "STYLE: Blueprint"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reading a film style", log_line=lambda i, o: f"Read the {o.style.get('name', '')} style.",
)
def style_get(ws: Workspace, inputs: GetIn) -> GetOut:
    from ... import styles

    s = styles.get(inputs.slug)
    if s is None:
        raise ValueError(f"no style called {inputs.slug}; see style.list")
    return GetOut(style=s, brief=styles.brief(inputs.slug))
