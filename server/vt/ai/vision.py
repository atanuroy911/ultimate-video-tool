"""A small vision model that looks at the video's own frames.

* `check_frame`: is anything cut off, overlapping, unreadable, empty or unrelated to the sentence? -> {ok, problems, fix_hint}
* `qa_project`: one frame per scene through the VLM, with deterministic pixel checks as the fallback when no vision model answers.
* `judge_picture`: shows the 3-6 candidate pictures for a word, the VLM picks the one that fits the sentence.
Everything is optional: no vision model means the pixel checks only and the rule/LLM picture choice stays.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image, ImageDraw

from . import AIUnavailable, complete_json, vision_provider
from ..util import ProgressFn, noop_progress, now_iso, write_json

FRAME_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "problems": {"type": "array", "maxItems": 5, "items": {"type": "string", "enum": ["cut_off", "overlap", "unreadable", "empty", "unrelated", "tiny_text", "other"]}},
        "fix_hint": {"type": "string", "maxLength": 160},
    },
    "required": ["ok", "problems"],
}

FRAME_PROMPT = """This is one frame of a short explainer video (a phone screen). The narrator is saying: "{sentence}"
Check ONLY these things and answer as JSON:
- cut_off: any text or picture cut off by the screen edge
- overlap: text or pictures covering each other so something is hard to read
- unreadable: text too small or too low-contrast to read
- empty: nothing meaningful on screen
- unrelated: the picture or graphic has nothing to do with the sentence
ok=true only if none of these apply. Be strict about cut_off, overlap and empty; do not complain about style."""

PICK_SCHEMA = {"type": "object", "properties": {"choice": {"type": "integer", "minimum": 0}, "reason": {"type": "string", "maxLength": 120}}, "required": ["choice"]}


def _png(im: Image.Image, max_side: int = 768) -> bytes:
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


# --------------------------------------------------------------------------- deterministic checks (no model)
def pixel_check(path: Path, aspect: str) -> list[str]:
    """Empty screen and content touching the left/right edge, measured on the pixels."""
    im = np.asarray(Image.open(path).convert("RGB")).astype("int16")
    h = im.shape[0]
    reg = im[: int(h * {"9:16": 0.72, "1:1": 0.74, "16:9": 0.74}.get(aspect, 0.74))]
    corners = np.concatenate([reg[:12, :12].reshape(-1, 3), reg[:12, -12:].reshape(-1, 3), reg[-12:, :12].reshape(-1, 3), reg[-12:, -12:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    fg = np.abs(reg.astype("int16") - bg).sum(axis=2) > 36
    out = []
    if fg.mean() < 0.012:
        out.append("empty")
    edge = 6
    if fg[:, :edge].mean() > 0.35 or fg[:, -edge:].mean() > 0.35:
        out.append("cut_off")
    return out


def edge_content(path: Path, aspect: str) -> float:
    """How much of the left, right and top edge strips is something other than the background (0-1, the worst strip). Nothing at
    the edges means nothing can be cut off there: used to confirm a vision model's "cut off" before it is believed."""
    im = np.asarray(Image.open(path).convert("RGB")).astype("int16")
    reg = im[: int(im.shape[0] * {"9:16": 0.72, "1:1": 0.74, "16:9": 0.74}.get(aspect, 0.74))]
    corners = np.concatenate([reg[:12, :12].reshape(-1, 3), reg[:12, -12:].reshape(-1, 3)])
    fg = np.abs(reg - np.median(corners, axis=0)).sum(axis=2) > 48
    e = 8
    return float(max(fg[:, :e].mean(), fg[:, -e:].mean(), fg[:e, :].mean()))


QUESTIONS = {
    "cut_off": "Look at the left, right and top edges of the image. Is any object, drawing, piece of furniture or text sliced by the image edge so that part of it is missing?",
    "overlap": "Is any text (a title, a label or a speech bubble) partly covered by, or drawn on top of, another text or shape so that letters are hidden?",
    "unreadable": "Is any text too small, too faint or too low in contrast against what is behind it to read easily on a phone?",
    "empty": "Is most of the image empty, with nothing meaningful to look at?",
}
YESNO = {"type": "object", "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}, "where": {"type": "string", "maxLength": 80}}, "required": ["answer"]}


def check_frame(png: Path, sentence: str, provider=None) -> dict:
    """One frame through the vision model, one focused yes/no question per problem: small models answer a single concrete question far
    better than a checklist (scripts/eval_vision.py on labelled frames, 2026-10-24: llama3.2-vision 0.83 precision / 0.83 recall this way,
    0.33 / 0.50 with the checklist). Each "yes" names where, which becomes the fix hint. Raises AIUnavailable without a vision model."""
    prov = provider or vision_provider()
    img = [_png(Image.open(png))]
    problems, where = [], []
    for k, q in QUESTIONS.items():
        r = complete_json("This is a frame of a vertical phone video. " + q + " Answer yes or no, and say where if yes.", YESNO, img, provider=prov,
                          max_tokens=80, timeout=120, temperature=0.0)
        if r.get("answer") == "yes":
            problems.append(k)
            if r.get("where"):
                where.append(f"{k.replace('_', ' ')}: {r['where']}")
    return {"ok": not problems, "problems": problems, "fix_hint": "; ".join(where)[:200].rsplit(" ", 1)[0] if len("; ".join(where)) > 200 else "; ".join(where)}


# --------------------------------------------------------------------------- the whole video
def _frames_from_video(video: Path, times: list[float], out: Path) -> list[Path]:
    import subprocess

    out.mkdir(parents=True, exist_ok=True)
    got = []
    for i, t in enumerate(times):
        f = out / f"frame-{i:02d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=540:-2", str(f)], capture_output=True)
        got.append(f)
    return got


def qa_project(project, progress: ProgressFn = noop_progress, provider=None, video: Optional[Path] = None, max_scenes: int = 0) -> dict:
    """One frame per scene, checked. Frames come from the rendered `video` when given (the only way to see a speaker's picture),
    else from the composition. `max_scenes` > 0 checks that many scenes spread over the video. Writes qa.json."""
    from ..compose import FORMATS, scene_timing
    from ..pipeline import compose_all
    from ..render.hyperframes import snapshot

    meta = project.meta()
    sf, beats = project.scenes(), project.beats()
    if not sf:
        raise ValueError("no plan yet")
    compose_all(project)
    cuts = project.cuts()
    dur = cuts.output_duration if cuts else max((w.end for w in project.transcript().kept()), default=1.0) + 0.5
    timing = scene_timing(sf, beats, dur)
    beat_by = {b.id: b for b in beats.beats}
    times = [round(t["start"] + min(3.2, 0.75 * (t["end"] - t["start"])), 2) for t in timing]
    scenes = list(sf.scenes)
    if max_scenes and len(scenes) > max_scenes:
        keep = sorted({round(i * (len(scenes) - 1) / (max_scenes - 1)) for i in range(max_scenes)})
        scenes, times = [scenes[i] for i in keep], [times[i] for i in keep]
    progress("qa", 0.05, "Capturing one frame per scene")
    frames = _frames_from_video(video, times, project.dir / "qa_frames") if video else snapshot(project.comp_dir / FORMATS[meta.aspect]["tag"], project.dir / "qa_frames", times)
    use_vlm = True
    try:
        prov = provider or vision_provider()
        use_vlm = prov.available() and prov.supports_images
    except AIUnavailable:
        use_vlm = False
    out = []
    model = ""
    for i, (sc, f) in enumerate(zip(scenes, frames)):
        progress("qa", 0.1 + 0.85 * i / max(1, len(frames)), f"Checking scene {i + 1} of {len(frames)}")
        sentence = " ".join(beat_by[b].text for b in sc.beats if b in beat_by)
        problems = list(pixel_check(f, meta.aspect))
        src, hint = "pixels", ""
        if use_vlm:
            try:
                r = check_frame(f, sentence, provider)
                seen = r["problems"]
                if "cut_off" in seen and "cut_off" not in problems and edge_content(f, meta.aspect) < 0.04:
                    seen = [x for x in seen if x != "cut_off"]           # the model says cut off, but nothing touches an edge: not believed
                problems = list(dict.fromkeys(problems + seen))
                hint = r.get("fix_hint", "")
                src = "vlm"
                model = (provider or vision_provider()).model()
            except AIUnavailable:
                use_vlm = False                        # one failure turns the model off for the rest of the run
        out.append({"id": sc.id, "t": times[i], "ok": not problems, "problems": problems, "fix_hint": hint, "source": src, "frame": f.name})
    res = {"at": now_iso(), "model": model, "scenes": out, "bad": [s["id"] for s in out if not s["ok"]]}
    write_json(project.dir / "qa.json", res)
    progress("qa", 1.0, f"{len(res['bad'])} of {len(out)} scenes need a look")
    return res


def fix_scenes(project, qa: dict) -> dict:
    """Automatic fixes for flagged scenes: crowded or cut-off scenes keep their main element; empty or unreadable scenes get rule-planner visual elements."""
    from ..planner import plan_rules
    from ..planning import refresh_scrims
    from ..schema import validate_scenes
    from ..planner.catalogue import all_icon_names

    sf = project.scenes()
    if not sf:
        return {"changed": []}
    tr, beats = project.transcript(), project.beats()
    beat_words = {b.id: b.word_ids for b in beats.beats} if beats else {}
    rules = None
    changed = []
    scenes = list(sf.scenes)
    flagged = {entry["id"]: set(entry.get("problems", [])) for entry in qa.get("scenes", []) if not entry.get("ok")}

    for i, sc in enumerate(scenes):
        probs = flagged.get(sc.id, set())
        # Also treat any scene with zero elements as having the 'empty' problem
        if not sc.elements:
            probs.add("empty")
        if not probs:
            continue

        new = None
        if probs & {"cut_off", "overlap"} and len(sc.elements) > 1:
            new = sc.model_copy(update={"elements": sc.elements[:1], "layout": "stack" if sc.layout in ("grid", "split", "side") else sc.layout})
        elif "empty" in probs or (probs & {"unreadable", "tiny_text"} and len(sc.elements) <= 1):
            rules = rules or plan_rules(tr, beats, project.meta().theme, language=project.meta().language)
            # Match rule scene by overlapping beats rather than requiring strict equality
            alt = next((r for r in rules.scenes if any(b in r.beats for b in sc.beats)), None)
            if alt and alt.elements:
                sc_words = set()
                for b in sc.beats:
                    sc_words.update(beat_words.get(b, []))
                matching = [e for e in alt.elements if e.at_word in sc_words]
                if not matching and sc_words:
                    first_w = sorted(sc_words, key=lambda w: int(w[1:]) if w[1:].isdigit() else 0)[0]
                    matching = [alt.elements[0].model_copy(update={"at_word": first_w})]
                if matching:
                    new = sc.model_copy(update={"elements": matching, "layout": "stack"})

        if new is not None:
            trial = sf.model_copy(update={"scenes": [new if k == i else s for k, s in enumerate(scenes)]})
            if not validate_scenes(trial, tr, beats, all_icon_names()):
                scenes[i] = new
                changed.append(sc.id)
    if changed:
        project.save_scenes(refresh_scrims(project, sf.model_copy(update={"scenes": scenes})))
    return {"changed": changed}


# --------------------------------------------------------------------------- picture judge
def render_candidates(cands: list[dict], workdir: Path) -> Path:
    """One image with the candidate pictures side by side, numbered 0..n-1 (drawn by the real renderer)."""
    from ..compose.composer import resolve_composition, write_composition
    from ..project import load_theme
    from ..render.hyperframes import snapshot
    from ..schema import Beat, Beats, ScenesFile, Transcript, Word

    n = len(cands)
    words = [Word(id=f"w{i + 1}", text=f"c{i}", start=i * 1.0 + 0.1, end=i * 1.0 + 0.6) for i in range(n)]
    beats = Beats(beats=[Beat(id=f"b{i + 1}", word_ids=[f"w{i + 1}"], start=i * 1.0, end=i * 1.0 + 0.9, text=f"c{i}") for i in range(n)])
    scenes = []
    for i, c in enumerate(cands):
        el = ({"type": "sticker", "emoji": c["id"], "label": "", "at_word": f"w{i + 1}"} if c["kind"] == "sticker"
              else {"type": "icon", "name": c["id"], "label": "", "at_word": f"w{i + 1}"})
        scenes.append({"id": f"s{i + 1}", "beats": [f"b{i + 1}"], "transition_in": "cut", "elements": [el]})
    sf = ScenesFile.model_validate({"theme": "minimal", "planner": "manual", "scenes": scenes})
    theme = load_theme("minimal")
    data = resolve_composition(sf, Transcript(words=words), beats, theme, "1:1", n * 1.0 + 0.5, None, language="en")
    data["captions_enabled"] = False
    data["captions"] = []
    idx = write_composition(workdir / "comp", data, theme)
    frames = snapshot(idx.parent, workdir / "snap", [i * 1.0 + 0.8 for i in range(n)])
    tiles = []
    for i, f in enumerate(frames):
        im = Image.open(f).convert("RGB")
        w, h = im.size
        im = im.crop((int(w * 0.18), int(h * 0.2), int(w * 0.82), int(h * 0.62))).resize((256, 220))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 40, 40), fill="black")
        d.text((14, 12), str(i), fill="white")
        tiles.append(im)
    sheet = Image.new("RGB", (256 * len(tiles), 220), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 256, 0))
    out = workdir / "candidates.png"
    sheet.save(out)
    return out


def judge_picture(word: str, sentence: str, cands: list[dict], workdir: Path, provider=None) -> Optional[int]:
    """Index of the candidate that best shows `word` in `sentence`, or None when the model cannot judge or none fits."""
    if len(cands) < 2:
        return 0 if cands else None
    sheet = render_candidates(cands, workdir)
    prompt = (f'Pictures numbered 0 to {len(cands) - 1} are shown left to right. Which one best illustrates the word "{word}" as used in this sentence: '
              f'"{sentence[:200]}"? Answer with the number as JSON. Choose -1 equivalent by picking the closest; never invent.')
    try:
        r = complete_json(prompt, {**PICK_SCHEMA, "properties": {**PICK_SCHEMA["properties"], "choice": {"type": "integer", "minimum": 0, "maximum": len(cands) - 1}}},
                          [_png(Image.open(sheet), 1400)], provider=provider or vision_provider(), max_tokens=120, timeout=180, temperature=0.0)
    except AIUnavailable:
        return None
    return int(r["choice"])


def improve_pictures(project, progress: ProgressFn = noop_progress, provider=None, max_scenes: int = 12) -> dict:
    """The VLM chooses between the dictionary's candidates for each stickered word, by looking at them. Changes only what it is sure differs."""
    import tempfile

    from ..planner import llm_plan
    from ..planning import refresh_scrims
    from ..schema import validate_scenes
    from ..planner.catalogue import all_icon_names
    from ..visuals import emoji as emo

    sf = project.scenes()
    tr, beats = project.transcript(), project.beats()
    words, beat_by = tr.by_id(), {b.id: b for b in beats.beats}
    changed, scenes = [], list(sf.scenes)
    jobs = [(i, k) for i, sc in enumerate(scenes) for k, e in enumerate(sc.elements) if e.type in ("sticker", "keyword") and getattr(e, "emoji", None)][:max_scenes]
    for n, (i, k) in enumerate(jobs):
        sc, e = scenes[i], scenes[i].elements[k]
        progress("pictures", n / max(1, len(jobs)), f"Looking at pictures for scene {i + 1}")
        w = words.get(e.at_word)
        if not w:
            continue
        sentence = " ".join(beat_by[b].text for b in sc.beats if b in beat_by)
        cands = llm_plan._options([w], sentence).get(w.id, [])
        cands = [c for c in cands if c["kind"] == "sticker"][:5]
        cur = emo.emoji_key(e.emoji)
        if cur and not any(c["id"] == cur for c in cands):
            cands.insert(0, {"id": cur, "kind": "sticker", "label": "current"})
        if len(cands) < 2:
            continue
        with tempfile.TemporaryDirectory() as d:
            pick = judge_picture(w.text, sentence, cands, Path(d), provider)
        if pick is None or cands[pick]["id"] == cur:
            continue
        new_el = e.model_copy(update={"emoji": cands[pick]["id"]})
        new = sc.model_copy(update={"elements": [new_el if j == k else x for j, x in enumerate(sc.elements)]})
        trial = sf.model_copy(update={"scenes": [new if j == i else s for j, s in enumerate(scenes)]})
        if not validate_scenes(trial, tr, beats, all_icon_names()):
            scenes[i] = new
            changed.append({"scene": sc.id, "word": w.text, "from": cur, "to": cands[pick]["id"]})
    if changed:
        project.save_scenes(refresh_scrims(project, sf.model_copy(update={"scenes": scenes})))
    progress("pictures", 1.0, f"{len(changed)} pictures changed")
    return {"changed": changed}
