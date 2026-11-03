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


class StoryKitIn(BaseModel):
    pass


class MotionKitOut(BaseModel):
    recipes: dict[str, list[dict[str,str]]] = Field(description="Every implemented entrance, transition and camera recipe, with readable names")
    point_schema: dict[str, Any] = Field(description="Validated keyframe contract shared by scene elements and additional visual tracks")
    workflow: list[str] = Field(description="How to apply motion through the same tools used by the editor")
    templates: list[dict[str,Any]] = Field(default_factory=list, description="Ready-to-use editable component starters, identical to the editor's Elements library")


@module(id="style.motion_kit",version=1,summary="Discover editable HyperFrames motion recipes and visual keyframes.",
    when_to_use="Choosing text animation, transitions, cameras or precise visual motion.",when_not_to_use="For generating new video footage.",
    inputs=StoryKitIn,outputs=MotionKitOut,requires=(),produces=(),cost=Cost("instant",("cpu",),.01),effects="none",determinism="pure",grounding=(),
    fallback=None,fallback_reason="Built-in deterministic animation recipes.",examples=(Example(inputs={},outputs={"recipes":{},"point_schema":{},"workflow":[]}),),
    toolboxes=("autonomous","studio","full"),plain_name="Motion and animation controls",log_line=lambda i,o:"Loaded editable motion recipes and keyframes.")
def motion_kit(ws: Workspace, inputs: StoryKitIn) -> MotionKitOut:
    from ...visual_motion import catalogue, MotionPoint
    from ...planner.catalogue import component_catalogue
    from ...planner.visual_templates import templates
    starters=[{k:t[k] for k in ('variant','name','category','starter')} for t in templates(component_catalogue())]
    return MotionKitOut(recipes=catalogue(),point_schema=MotionPoint.model_json_schema(),templates=starters,workflow=[
        "Read the visual schema and current timeline before editing. Keep all text and data grounded in the supplied material.",
        "Use timeline.edit_scene with operation edit_element, scene_id, index and patch containing entrance and/or keyframes. Each motion point has video time, x, y, scale, rotation, opacity and ease. Points must be ordered and unique.",
        "For added text and media, use timeline.layers with the same keyframes on the clip. Preserve other tracks and fields.",
        "Use timeline.edit_scene patch for transition_effect and camera_move on a scene. Select valid ids from recipes, auto or none.",
        "Render snapshots before, during and after motion; check readability and exact cuts. The editor, live preview and export share these controls."])


class StoryKitOut(BaseModel):
    character_styles: list[str] = Field(description="Reusable character drawing styles.")
    environments: list[str] = Field(description="Built-in scene environments.")
    cameras: list[str] = Field(description="Deterministic camera moves.")
    lighting: list[str] = Field(description="Scene lighting presets.")
    text_treatments: list[str] = Field(description="Text treatments for signs and other environmental lettering.")
    component_schema: dict[str, Any] = Field(description="Complete editable cartoon component schema, including cast, cues, labels and props.")
    workflow: list[str] = Field(description="Grounded steps for making repeatable animated videos with the installed models.")


@module(
    id="style.story_kit", version=1, summary="Get the reusable animated-story kit, editable controls and code-free production workflow.",
    when_to_use="Making repeatable cartoon shorts with consistent characters, sets and generated props.",
    when_not_to_use="For photorealistic footage or arbitrary generated application code.",
    inputs=StoryKitIn, outputs=StoryKitOut, requires=(), produces=(),
    cost=Cost("instant", ("cpu",), .01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Built-in templates need no remote service.",
    examples=(Example(inputs={}, outputs={"character_styles":["classic","ink","paper"],
        "environments":["plain","village","market","home","office","classroom","street","nature","studio","shop"],
        "cameras":["still","push","pull","pan"],"lighting":["day","sunset","night"],
        "text_treatments":["sign","chalk","paint","neon"],"component_schema":{},
        "workflow":["Read the supplied facts, choose a reusable cast and environment, place editable cartoon elements and inspect rendered frames."]}),),
    toolboxes=("autonomous","studio","full"), plain_name="Animated story kit",
    log_line=lambda i,o: f"Loaded {len(o.character_styles)} character styles and {len(o.environments)} environments.",
)
def story_kit(ws: Workspace, inputs: StoryKitIn) -> StoryKitOut:
    from ...schema import Cartoon
    schema = Cartoon.model_json_schema()
    fields = schema['properties']
    return StoryKitOut(
        character_styles=fields['character_style']['enum'], environments=fields['set']['enum'],
        cameras=fields['camera']['enum'], lighting=fields['lighting']['enum'],
        text_treatments=schema['$defs']['CartoonLabel']['properties']['treatment']['enum'],
        component_schema=schema,
        workflow=[
            "Read the user's script and craft.rules. Ground every fact, quotation and label in supplied or verified material.",
            "Choose one character style. Reuse each character's name and who fields across scenes; choose a set, lighting and camera per scene.",
            "Use the installed image generation tools for missing props. Save them to project media, optionally remove the background, and reuse their media IDs with exact fractional x/y/width/height.",
            "Build cartoon components from this schema. Place them with fill.graphic and timeline.place, or edit existing scenes with timeline.edit_scene. Add labels as sign, chalk, paint or neon. Keep captions as their own editable track.",
            "Inspect rendered previews, check readability and timing, then export. All scenes, cast, text and image props remain editable. No per-video application code is generated.",
        ])
