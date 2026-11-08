"""Free visual timing. Narration ownership is metadata, not an editing constraint."""
from math import isfinite

from .compose.composer import scene_timing
from .scene_ops import OpError, _find, _next_id
from .schema import Scene


def freeze_starts(sf, beats, duration):
    times = scene_timing(sf, beats, duration)
    return sf.model_copy(update={"scenes": [s.model_copy(update={"start": t["start"]}) for s, t in zip(sf.scenes, times)]})


def move_edge(sf, beats, duration, sid, at):
    i = _find(sf, sid)
    if i + 1 == len(sf.scenes):
        raise OpError("The last scene ends with the video")
    times = scene_timing(sf, beats, duration)
    if not isfinite(at) or not times[i]["start"] + .02 <= at <= times[i+1]["end"] - .02:
        raise OpError("Keep at least 0.02 seconds on each side of the scene change")
    out = freeze_starts(sf, beats, duration)
    out.scenes[i+1] = out.scenes[i+1].model_copy(update={"start": round(at, 3)})
    return out


def split_at(sf, beats, duration, sid, at, resolved):
    i = _find(sf, sid)
    times = scene_timing(sf, beats, duration)
    t = times[i]
    if not isfinite(at) or not t["start"] + .02 <= at <= t["end"] - .02:
        raise OpError("Place the split inside the scene")
    out = freeze_starts(sf, beats, duration)
    sc = out.scenes[i]
    # Existing visual clips retain their exact ranges across the new scene change.
    els = []
    for k, el in enumerate(sc.elements):
        timing = resolved.get(f"{sid}:{k}", {"start": t["start"], "end": t["end"]})
        els.append(el.model_copy(update={"start": el.start if el.start is not None else timing["start"],
                                         "end": el.end if el.end is not None else timing["end"]}))
    stick = {**sc.stick, "actions": [{**a, "_timed": True} for a in sc.stick.get("actions", [])]} if sc.stick else None
    first = sc.model_copy(update={"elements": els, "stick": stick})
    data = sc.model_dump()
    data.update(id=_next_id(sf), start=round(at, 3), beats=[], elements=[], stick=None, caption={"highlight_words": []}, transition_in="cut", sfx=[])
    second = Scene.model_validate(data)
    out.scenes[i:i+1] = [first, second]
    return out


def resolved_elements(data):
    result = {}
    for sc in data.get("scenes", []):
        for i, el in enumerate(sc.get("elements", [])):
            key = f"{sc.get('src', sc['id'])}:{el.get('_i', i)}"
            result[key] = {"start": el["at"], "end": el.get("until", sc["end"])}
    return result


def project_element_times(project):
    from .compose import FORMATS
    from .util import read_json
    return resolved_elements(read_json(project.comp_dir / FORMATS[project.meta().aspect]["tag"] / "data.json", {}) or {})


def edit_element(sf, sid, index, patch, resolved):
    """One shared visual edit for Studio, CLI and Director modules."""
    from .scene_ops import patch_scene
    sc = sf.scenes[_find(sf, sid)]
    if not 0 <= index < len(sc.elements):
        raise OpError("This visual no longer exists")
    els = [e.model_dump() for e in sc.elements]
    # Every other picture of the scene keeps the times it shows now: without this, the composer re-pages the scene around the edited one and the
    # neighbours move (a sticker ends later, the next picture is pulled to the scene start) although the person never touched them.
    for j, e in enumerate(els):
        t = resolved.get(f"{sid}:{j}")
        if j != index and t and e.get("start") is None and e.get("end") is None:
            e["start"], e["end"] = round(t["start"], 3), round(t["end"], 3)
    if patch.get("delete"):
        els.pop(index)
    elif "split" in patch:
        t = float(patch["split"])
        timing = resolved.get(f"{sid}:{index}")
        if not timing or not isfinite(t) or not timing["start"] + .02 <= t <= timing["end"] - .02:
            raise OpError("Place the split inside the visual")
        el = els[index]
        second = {**el, "id": None, "start": t, "end": timing["end"], "edited": True}
        if el["type"] in ("media_frame", "device"):
            second["offset"] = el.get("offset", 0) + t - timing["start"]
        els[index:index+1] = [{**el, "start": timing["start"], "end": t, "edited": True}, second]
    elif patch.get("duplicate"):
        els[index]["edited"] = True
        els.insert(index+1, {**els[index], "id": None})
    else:
        timing = resolved.get(f"{sid}:{index}", {})
        if "start" in patch and "end" in patch and patch["start"] is not None and patch["end"] is not None and "keyframes" not in patch and els[index].get("keyframes"):
            old_start = els[index].get("start") if els[index].get("start") is not None else timing.get("start", 0)
            old_end = els[index].get("end") if els[index].get("end") is not None else timing.get("end", old_start)
            delta = patch["start"] - old_start
            if abs((patch["end"]-old_end)-delta)<.002:
                els[index]["keyframes"] = [{**p,"time":round(p["time"]+delta,3)} for p in els[index]["keyframes"]]
        els[index].update(patch)
        els[index]["edited"] = True
    return patch_scene(sf, sid, {"elements": els})


def retime_manual(sf, old_cuts, new_cuts, clock):
    """Ripple explicit visual timings with voice edits; retain source anchors for undo."""
    from .audio_edit import out_to_src
    from .schema import ScenesFile
    data = sf.model_dump()
    updated = {}
    def shift(obj, field, key):
        value = obj.get(field)
        if value is None:
            return
        previous = clock.get(key, {})
        source = previous.get("source") if previous.get("output") == value else out_to_src(old_cuts, value)
        if source is None:
            source = old_cuts.source_duration + max(0, value-old_cuts.output_duration)
        target = round(new_cuts.map_time_nearest(source), 3)
        obj[field] = target
        updated[key] = {"output": target, "source": source}
    for sc in data["scenes"]:
        shift(sc, "start", sc["id"]+":start")
        for i, el in enumerate(sc["elements"]):
            for field in ("start", "end"):
                shift(el, field, f"{sc['id']}:{i}:{field}")
            last_time = -36001
            for j, point in enumerate(el.get("keyframes") or []):
                key = f"{sc['id']}:{i}:motion:{j}"
                if point["time"] >= 0:
                    shift(point, "time", key)
                # A removed interval may collapse several points onto one boundary.
                # Retain their identities and source anchors so undo can restore them.
                point["time"] = round(max(point["time"], last_time + .001), 3)
                if key in updated:
                    updated[key]["output"] = point["time"]
                last_time = point["time"]
            if el.get("end") is not None and el.get("start") is not None and el["end"] <= el["start"]:
                el["end"] = round(el["start"]+.001, 3)
                updated[f"{sc['id']}:{i}:end"]["output"] = el["end"]
        for i, action in enumerate((sc.get("stick") or {}).get("actions", [])):
            if action.get("_timed"):
                for field in ("start", "end"):
                    shift(action, field, f"{sc['id']}:action:{i}:{field}")
    return ScenesFile.model_validate(data), updated
