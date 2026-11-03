"""Checks and automatic repair of a Video Script against the transcript. Errors are written so a model can fix them in one go."""
from __future__ import annotations

import copy
import re
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from ..schema import Beats, Element, Transcript
from . import catalogue as C
from .models import VideoScript

_EL = TypeAdapter(Element)
REQUIRED = {v: req for v, (_, _, req) in C.VERBS.items()}


def _scene_words(sc: dict, beats_by: dict) -> list[str]:
    out: list[str] = []
    for b in sc.get("beats", []):
        if b in beats_by:
            out += beats_by[b].word_ids
    return out


def _set_of(script: dict, sc: dict) -> Optional[dict]:
    sid = sc.get("set")
    return next((s for s in script.get("sets", []) if s.get("id") == sid), None)


def _targets(script: dict, sc: dict) -> set[str]:
    st = _set_of(script, sc)
    props = set(st.get("props", [])) | set(C.SETS.get(st.get("kind", "plain"), ())) if st else set()
    return props | {c.get("id") for c in script.get("cast", [])} | set(C.SPECIAL_TARGETS)


# --------------------------------------------------------------------------- validation
def validate_script(data: dict, tr: Transcript, beats: Beats, icons: Optional[set[str]] = None, media_ids: Optional[set[str]] = None) -> list[str]:
    """Plain-language problems (empty list = valid). `data` is the raw dict so unknown fields are reported, not hidden."""
    try:
        script = VideoScript.model_validate(data)
    except ValidationError as e:
        return [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()][:12]
    errs: list[str] = []
    words, beats_by = tr.by_id(), {b.id: b for b in beats.beats}
    expected = [b.id for b in beats.beats]
    seen = [b for s in script.scenes for b in s.beats]
    for s in script.scenes:
        for b in s.beats:
            if b not in beats_by:
                errs.append(f"scene {s.id}: unknown beat '{b}'")
    missing = [b for b in expected if b not in seen]
    if missing:
        errs.append(f"beats not covered by any scene: {missing}")
    if len(seen) != len(set(seen)):
        errs.append("a beat appears in more than one scene")
    elif not missing and seen != expected:
        errs.append("scene beats must follow the original beat order")
    ids = [s.id for s in script.scenes]
    if len(ids) != len(set(ids)):
        errs.append("scene ids must be unique")
    cast_ids = [c.id for c in script.cast]
    if len(cast_ids) != len(set(cast_ids)):
        errs.append("cast ids must be unique")
    set_ids = [s.id for s in script.sets]
    if len(set_ids) != len(set(set_ids)):
        errs.append("set ids must be unique")
    for c in script.cast:
        if c.kind == "emoji" and not (c.emoji or c.name):
            errs.append(f"cast '{c.id}': an emoji actor needs `emoji` (for example '1f98a') or a `name` the sticker can be found by")
    d = script.model_dump(by_alias=True)
    if script.kind in ("stick", "cartoon"):
        if not script.cast:
            errs.append("kind 'stick' needs at least one cast member")
        if not script.sets:
            errs.append("kind 'stick' needs at least one set")
    for sc_model, sc in zip(script.scenes, d["scenes"]):
        wset = set(_scene_words(sc, beats_by))
        where = f"scene {sc['id']}"
        if sc.get("set") and sc["set"] not in set_ids:
            errs.append(f"{where}: set '{sc['set']}' is not defined; sets: {', '.join(set_ids) or 'none'}")
        if script.kind in ("stick", "cartoon") and (sc["actions"] or sc["set"]) and not sc.get("set") and script.sets:
            errs.append(f"{where}: needs a `set`")
        targets = _targets(d, sc)
        cam = sc.get("camera") or {}
        if cam.get("move") == "zoom_to":
            f = cam.get("focus")
            if not f:
                errs.append(f"{where}: camera move 'zoom_to' needs `focus` (a prop or a cast id of this scene)")
            elif f not in targets and f not in {a.get("prop") for a in sc["actions"]}:
                errs.append(f"{where}: camera focus '{f}' is not a prop of set '{sc.get('set')}' or a cast id; options: {', '.join(sorted(targets))}")
        for i, a in enumerate(sc["actions"], 1):
            w = f"{where} action {i} ({a['do']})"
            if a["at_word"] not in words:
                errs.append(f"{w}: at_word '{a['at_word']}' is not a transcript word")
            elif a["at_word"] not in wset:
                errs.append(f"{w}: at_word '{a['at_word']}' is outside this scene's beats")
            if a["who"] not in cast_ids:
                errs.append(f"{w}: who '{a['who']}' is not in the cast ({', '.join(cast_ids) or 'empty'})")
            for need in REQUIRED[a["do"]]:
                key = {"from": "from", "to_side": "to_side"}.get(need, need)
                if a.get(key) in (None, ""):
                    errs.append(f"{w}: '{a['do']}' needs `{need}`")
            tg = a.get("target")
            if tg and tg not in targets:
                errs.append(f"{w}: target '{tg}' is not a prop of set '{sc.get('set')}' or a cast id; options: {', '.join(sorted(targets))}")
        times = [words[a["at_word"]].start for a in sc["actions"] if a["at_word"] in words]
        if times != sorted(times):
            errs.append(f"{where}: actions must be listed in the order they are spoken")
        for i, o in enumerate(sc["overlays"], 1):
            w = f"{where} overlay {i}"
            if script.kind == "emoji" and o.get("type") not in ("sticker", "keyword"):
                errs.append(f"{w}: kind 'emoji' only allows `sticker` and `keyword` overlays, not '{o.get('type')}'")
        if script.kind == "emoji" and sc["actions"]:
            errs.append(f"{where}: kind 'emoji' has no characters, leave `actions` empty")
        for i, o in enumerate(sc["overlays"], 1):
            w = f"{where} overlay {i}"
            at = o.get("at_word")
            if at not in words:
                errs.append(f"{w}: at_word '{at}' is not a transcript word")
            elif at not in wset:
                errs.append(f"{w}: at_word '{at}' is outside this scene's beats")
            try:
                el = _EL.validate_python(o)
            except ValidationError as e:
                errs += [f"{w}: {'.'.join(str(x) for x in err['loc'][1:])}: {err['msg']}" for err in e.errors()][:3]
                continue
            if icons is not None:
                names = [el.name] if el.type == "icon" else [el.icon] if el.type in ("icon_row", "keyword") else [x.icon for x in el.items] if el.type == "feature_grid" else []
                errs += [f"{w}: unknown icon '{n}'" for n in names if n and n != "coin" and n not in icons]
            mid = getattr(el, "media", None) if el.type in ("device", "media_frame") else None
            if mid and media_ids is not None and mid not in media_ids:
                errs.append(f"{w}: media '{mid}' is not in the project's media bin")
        for c in sc["sfx"]:
            if c["at_word"] not in wset:
                errs.append(f"{where}: sfx at_word '{c['at_word']}' is outside this scene")
        for wid in sc["highlight_words"]:
            if wid not in wset:
                errs.append(f"{where}: highlight word '{wid}' is outside this scene")
    return errs


# --------------------------------------------------------------------------- repair
def _num(wid: Any) -> Optional[int]:
    m = re.fullmatch(r"w(\d+)", str(wid))
    return int(m.group(1)) if m else None


def _nearest(wid: Any, pool: list[str]) -> Optional[str]:
    """The word of `pool` closest to a (wrong) id: by number if it has one, else the first."""
    if not pool:
        return None
    n = _num(wid)
    if n is None:
        return pool[0]
    return min(pool, key=lambda p: abs((_num(p) or 0) - n))


def _norm_key(s: Any) -> str:
    return re.sub(r"[\s\-]+", "_", str(s).strip().lower())


def _truncate_overlay(o: dict) -> dict:
    """Shorten strings that exceed the element's length limits (pydantic names the exact place)."""
    for _ in range(12):
        try:
            _EL.validate_python(o)
            return o
        except ValidationError as e:
            fixed = False
            for err in e.errors():
                if err["type"] == "string_too_long":
                    ref: Any = o
                    for k in err["loc"][1:-1]:
                        ref = ref[k]
                    last = err["loc"][-1]
                    lim = err["ctx"]["max_length"]
                    ref[last] = ref[last][:max(1, lim - 1)].rstrip() + ("…" if lim > 8 else "")
                    fixed = True
                elif err["type"] == "too_long" and len(err["loc"]) > 1:
                    ref = o
                    for k in err["loc"][1:-1]:
                        ref = ref[k]
                    del ref[err["loc"][-1]][err["ctx"]["max_length"]:]
                    fixed = True
            if not fixed:
                return o
    return o


def repair_script(data: dict, tr: Transcript, beats: Beats, kind: Optional[str] = None) -> dict:
    """Fix what is safely fixable: synonyms, wrong word ids, over-long text, missing/misordered beats. Never invents content."""
    s = copy.deepcopy(data) if isinstance(data, dict) else {}
    words, beats_by = tr.by_id(), {b.id: b for b in beats.beats}
    s.setdefault("version", "1.0")
    s.setdefault("scenes", [])
    if kind in C.KINDS:
        s["kind"] = kind                                   # what was asked for wins over what the model wrote
    if s.get("kind") not in C.KINDS:
        s["kind"] = "explainer"
    if s.get("kind") == "emoji":                       # the mode wins over what the model wrote: only emoji and type, no characters
        s["cast"], s["sets"] = [], []
        for sc in s.get("scenes", []):
            if isinstance(sc, dict):
                sc["actions"] = []
                sc["set"] = None
                sc["overlays"] = [o for o in (sc.get("overlays") or []) if isinstance(o, dict) and o.get("type") in ("sticker", "keyword")]
    s["cast"] = [c for c in s.get("cast", []) if isinstance(c, dict)]
    for c in s["cast"]:
        c["id"] = _norm_key(c.get("id", "narrator"))[:16] or "narrator"
        if c.get("role") not in C.ROLES:
            c["role"] = "narrator"
        if c.get("rig") not in C.RIGS:
            c["rig"] = "stick-basic"
        st = c.get("style")
        if isinstance(st, dict):
            if st.get("head") not in C.HEADS:
                st["head"] = "round"
            if st.get("accessory") not in C.ACCESSORIES:
                st["accessory"] = "none"
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(st.get("color", ""))):
                st.pop("color", None)
    s["sets"] = [x for x in s.get("sets", []) if isinstance(x, dict)]
    for x in s["sets"]:
        x["id"] = _norm_key(x.get("id", x.get("kind", "plain")))[:16]
        if x.get("kind") not in C.SETS:
            x["kind"] = "plain"
    has_actions = any(isinstance(sc, dict) and sc.get("actions") for sc in s["scenes"])
    if s.get("kind") in ("stick", "cartoon") or has_actions:        # models often forget to declare who acts and where: derive it from what the scenes use
        used = [a.get("who") for sc in s["scenes"] if isinstance(sc, dict) for a in (sc.get("actions") or []) if isinstance(a, dict) and a.get("who")]
        have = {c["id"] for c in s["cast"]}
        for who in dict.fromkeys(_norm_key(u) for u in used):
            if who and who not in have and len(s["cast"]) < 8:
                s["cast"].append({"id": who[:16], "role": "narrator"})
        if not s["cast"]:
            s["cast"].append({"id": "maya", "role": "teacher"})
        have_sets = {x["id"] for x in s["sets"]}
        for sc in s["scenes"]:
            if isinstance(sc, dict) and sc.get("set") and _norm_key(sc["set"])[:16] not in have_sets and len(s["sets"]) < 8:
                nm = _norm_key(sc["set"])[:16]
                s["sets"].append({"id": nm, "kind": nm if nm in C.SETS else "plain"})
                have_sets.add(nm)
        if not s["sets"]:
            s["sets"].append({"id": "main", "kind": "plain"})
    cast_ids = [c["id"] for c in s["cast"]]
    # scenes: keep only known beats, drop empty/duplicate, then cover what is missing, in order
    used: set[str] = set()
    scenes = []
    for sc in s["scenes"]:
        if not isinstance(sc, dict):
            continue
        sc["beats"] = [b for b in sc.get("beats", []) if b in beats_by and not (b in used or used.add(b))]
        if sc["beats"]:
            scenes.append(sc)
    order = {b.id: i for i, b in enumerate(beats.beats)}
    scenes.sort(key=lambda sc: order[sc["beats"][0]])
    covered = {b for sc in scenes for b in sc["beats"]}
    for b in beats.beats:
        if b.id not in covered:
            scenes.append({"id": f"x{b.id}", "beats": [b.id], "overlays": [], "actions": []})
    scenes.sort(key=lambda sc: order[sc["beats"][0]])
    flat = [b for sc in scenes for b in sc["beats"]]
    if flat != [b.id for b in beats.beats]:                   # interleaved scenes: fall back to one scene per beat
        scenes = [{"id": "", "beats": [b.id], "overlays": [], "actions": []} for b in beats.beats]
    for i, sc in enumerate(scenes, 1):
        sc["id"] = f"s{i}"
        pool = []
        for b in sc["beats"]:
            pool += beats_by[b].word_ids
        pool = [w for w in pool if w in words]
        sc["camera"] = sc.get("camera") if isinstance(sc.get("camera"), dict) else {}
        if sc["camera"].get("shot") not in C.SHOTS:
            sc["camera"].pop("shot", None)
        if sc["camera"].get("move") not in C.MOVES:
            sc["camera"].pop("move", None)
        if sc.get("set") and sc["set"] not in [x["id"] for x in s["sets"]]:
            match = next((x["id"] for x in s["sets"] if x["kind"] == sc["set"]), None)
            sc["set"] = match or (s["sets"][0]["id"] if s["sets"] else None)
        if sc.get("set") is None and s.get("kind") in ("stick", "cartoon") and s["sets"]:
            sc["set"] = s["sets"][0]["id"]
        if sc.get("set") is None and s["sets"] and s.get("kind") in ("stick", "cartoon"):
            sc["set"] = s["sets"][0]["id"]
        acts = []
        for a in sc.get("actions", []) or []:
            if not isinstance(a, dict):
                continue
            a = {k: v for k, v in a.items() if v is not None}
            if "from_" in a:
                a["from"] = a.pop("from_")
            do = _norm_key(a.get("do", ""))
            a["do"] = C.VERB_SYNONYMS.get(do, do)
            if a["do"] not in C.VERBS:
                continue
            if a.get("at_word") not in pool:
                a["at_word"] = _nearest(a.get("at_word"), pool)
            if a.get("who") not in cast_ids:
                a["who"] = cast_ids[0] if cast_ids else a.get("who")
            if a.get("emotion"):
                e = _norm_key(a["emotion"])
                a["emotion"] = C.EMOTION_SYNONYMS.get(e, e)
                if a["emotion"] not in C.EMOTIONS:
                    a["emotion"] = "neutral"
            if a["do"] == "react" and not a.get("emotion"):
                a["emotion"] = "happy"
            if a["do"] == "walk_in" and not a.get("from"):
                a["from"] = "left"
            if a["do"] == "walk_out" and not a.get("to_side"):
                a["to_side"] = "right"
            if a["do"] == "turn" and not a.get("side"):
                a["side"] = "right"
            for k in ("from", "to_side", "side"):
                if k in a and a[k] not in ("left", "right"):
                    a.pop(k)
            if a["do"] == "count" and not a.get("count"):
                a["count"] = 1
            for k, lim in (("bubble", 70), ("target", 24), ("prop", 24)):
                if isinstance(a.get(k), str) and len(a[k]) > lim:
                    a[k] = a[k][:lim - 1].rstrip() + "…"
            if isinstance(a.get("to"), (int, float)):
                a["to"] = min(1.0, max(0.0, float(a["to"])))
            if a.get("target") and a["target"] not in _targets(s, sc):          # a prop the set lacks: the prop is added to the set
                st = _set_of(s, sc)
                if st is not None and a["do"] in ("point", "look_at") and len(st.setdefault("props", [])) < 8:
                    st["props"].append(a["target"])
            acts.append(a)
        acts.sort(key=lambda a: words[a["at_word"]].start if a.get("at_word") in words else 1e9)
        sc["actions"] = [a for a in acts if a.get("at_word") in words]
        ov = []
        for o in sc.get("overlays", []) or []:
            if not isinstance(o, dict):
                continue
            if o.get("at_word") not in pool:
                o["at_word"] = _nearest(o.get("at_word"), pool)
            o = _truncate_overlay(o)
            try:
                _EL.validate_python(o)
            except ValidationError:                       # still invalid (e.g. one stat in a stat row): drop it, never invent content
                continue
            ov.append(o)
        ov.sort(key=lambda o: words[o["at_word"]].start if o.get("at_word") in words else 1e9)
        sc["overlays"] = ov
        sc["sfx"] = [dict(c, at_word=c["at_word"] if c.get("at_word") in pool else _nearest(c.get("at_word"), pool)) for c in sc.get("sfx", []) or []
                     if isinstance(c, dict) and c.get("id") in C.SFX]
        sc["highlight_words"] = [w for w in sc.get("highlight_words", []) if w in pool][:3]
    s["scenes"] = scenes
    return s
