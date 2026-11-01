"""Video Script <-> scenes.json. `compile_script` makes the plan the renderer uses; `script_from_scenes` writes today's plans in the contract."""
from __future__ import annotations

from typing import Optional

from ..schema import Beats, Scene, ScenesFile, Transcript
from . import catalogue as C
from .models import VERSION, ScriptScene, VideoScript


def _timeline(sc: ScriptScene, script: VideoScript, tr: Transcript, beats_by: dict) -> dict:
    """Actions with seconds. One character does one thing at a time: an action that starts while the same character is still busy is queued."""
    words = tr.by_id()
    t_end = beats_by[sc.beats[-1]].end
    busy: dict[str, float] = {}
    acts = []
    for a in sc.actions:
        start = max(words[a.at_word].start, busy.get(a.who, 0.0))
        end = min(start + C.verb_seconds(a.do), max(start + 0.2, t_end))
        busy[a.who] = end
        d = a.model_dump(by_alias=True, exclude_none=True)
        d.update(start=round(start, 3), end=round(end, 3))
        acts.append(d)
    st = next((x for x in script.sets if x.id == sc.set), None)
    return {"set": {"id": st.id, "kind": st.kind, "props": list(dict.fromkeys(([] if st.art else list(C.SETS.get(st.kind, ()))) + st.props)), "time": st.time, "weather": st.weather, "art": st.art} if st else None,
            "camera": sc.camera.model_dump(), "cast": [c.model_dump() for c in script.cast], "actions": acts}


def compile_script(script: VideoScript, tr: Transcript, beats: Beats, theme: str = "paper") -> ScenesFile:
    beats_by = {b.id: b for b in beats.beats}
    scenes = []
    for sc in script.scenes:
        els = sorted(sc.overlays, key=lambda o: tr.by_id()[o["at_word"]].start)
        scenes.append(Scene.model_validate({
            "id": sc.id, "beats": sc.beats, "layout": ("upper" if script.kind in ("stick", "cartoon") and sc.layout == "stack" else sc.layout), "transition_in": sc.transition_in, "tone": sc.tone,
            "archetype": "stick" if script.kind in ("stick", "cartoon") else (sc.archetype or ("emoji" if script.kind == "emoji" else None)), "role": sc.role,
            "elements": els, **({"backdrop": sc.backdrop} if sc.backdrop else {}),
            "caption": {"highlight_words": sc.highlight_words},
            "stick": _timeline(sc, script, tr, beats_by) if script.kind in ("stick", "cartoon") or sc.actions else None,
            "sfx": [c.model_dump() for c in sc.sfx],
        }))
    return ScenesFile(theme=theme, planner=script.planner, scenes=scenes)


def script_from_scenes(sf: ScenesFile, language: str = "en", aspect: str = "9:16", title: str = "") -> VideoScript:
    """Today's plans expressed in the contract (no cast, no actions): overlays are the elements."""
    scenes = []
    for s in sf.scenes:
        d = s.model_dump(exclude_none=True)
        scenes.append(ScriptScene.model_validate({
            "id": s.id, "beats": s.beats, "layout": s.layout, "transition_in": s.transition_in, "tone": s.tone, "archetype": s.archetype,
            "role": s.role, "overlays": d.get("elements", []), "backdrop": d.get("backdrop"),
            "highlight_words": s.caption.highlight_words, "sfx": s.sfx}))
    return VideoScript.model_validate({"version": VERSION, "kind": "explainer", "meta": {"title": title, "language": language, "aspect": aspect},
                                       "scenes": [x.model_dump(by_alias=True) for x in scenes], "planner": sf.planner})


def to_json_schema() -> dict:
    return VideoScript.model_json_schema(by_alias=True)
