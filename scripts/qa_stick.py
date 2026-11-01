"""Real check of the stick-figure animations for the common patterns: each pattern is a Video Script (validated with the app's own validator, compiled to scenes), rendered by
HyperFrames, and four frames per pattern are looked at: the figure must be drawn, must change between frames (a still figure is not an animation), and must stay inside the picture
(except while it walks on or off). Contact sheets are written for a human to look at too.

    python scripts/qa_stick.py [--aspects 9:16,16:9] [--out qa_out_stick] [--only greeting,teaching]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vt import paths  # noqa: E402
from vt.compose.composer import resolve_composition, write_composition  # noqa: E402
from vt.project import load_theme  # noqa: E402
from vt.render.hyperframes import snapshot  # noqa: E402
from vt.script import compile_script, repair_script, validate_script  # noqa: E402
from vt.script.examples import make  # noqa: E402
from vt.util import read_json  # noqa: E402
from vt.visuals import icons as icon_sets  # noqa: E402
from vt.planner.catalogue import all_icon_names  # noqa: E402

A = lambda k, who, do, **x: {"k": k, "who": who, "do": do, **x}  # noqa: E731  (k: index of the word in the scene's sentence where it starts)

PATTERNS: dict[str, dict] = {
    "greeting": {"cast": [("maya", "teacher")], "sets": {"set": "classroom"}, "scenes": [
        ("Hello everyone and welcome to the class today", "set", [A(0, "maya", "walk_in", **{"from": "left", "to": 0.45}), A(2, "maya", "wave"), A(5, "maya", "say", bubble="Welcome!")], "medium", "push_in")]},
    "teaching": {"cast": [("maya", "teacher")], "sets": {"set": "classroom"}, "scenes": [
        ("Look at the board here because the answer is written there", "set", [A(0, "maya", "point", target="board"), A(3, "maya", "explain"), A(7, "maya", "write_board", bubble="2 + 2 = 4")], "medium", "none")]},
    "dialogue": {"cast": [("ana", "student"), ("raj", "friend")], "sets": {"set": "street"}, "scenes": [
        ("Where are you going asked Ana and Raj said to the shop", "set", [A(0, "ana", "say", bubble="Where are you going?"), A(5, "raj", "say", bubble="To the shop"), A(8, "raj", "point", target="shop")], "wide", "none")]},
    "meeting": {"cast": [("ana", "boss"), ("raj", "worker")], "sets": {"set": "office"}, "scenes": [
        ("They met in the office and shook hands to start the deal", "set", [A(0, "ana", "walk_in", **{"from": "left", "to": 0.3}), A(0, "raj", "walk_in", **{"from": "right", "to": 0.7}), A(5, "ana", "handshake", target="raj")], "medium", "none")]},
    "celebration": {"cast": [("ana", "friend"), ("raj", "friend")], "sets": {"set": "stage"}, "scenes": [
        ("We won the prize so everyone cheered and jumped with joy", "set", [A(0, "ana", "celebrate"), A(3, "raj", "jump"), A(6, "ana", "high_five", target="raj")], "medium", "push_in")]},
    "thinking": {"cast": [("sam", "student")], "sets": {"set": "home"}, "scenes": [
        ("He was not sure what to do so he thought about it for a while", "set", [A(0, "sam", "shrug"), A(4, "sam", "think"), A(10, "sam", "react", emotion="confused")], "close", "none")]},
    "shopping": {"cast": [("ana", "customer"), ("raj", "seller")], "sets": {"set": "market"}, "scenes": [
        ("She bought three apples from the seller and carried them home", "set", [A(0, "ana", "walk_in", **{"from": "left", "to": 0.35}), A(2, "ana", "count", count=3), A(5, "ana", "carry", prop="basket"), A(8, "ana", "walk_out", to_side="right")], "wide", "follow")]},
    "chase": {"cast": [("ana", "friend")], "sets": {"set": "nature"}, "scenes": [
        ("She ran across the park and then turned around and stopped", "set", [A(0, "ana", "walk_in", **{"from": "left", "to": 0.3}), A(2, "ana", "run", to=0.8), A(6, "ana", "turn", side="left"), A(8, "ana", "idle")], "wide", "pan_right")]},
    "accident": {"cast": [("sam", "friend")], "sets": {"set": "street"}, "scenes": [
        ("He tripped on the stone and fell and that was embarrassing", "set", [A(0, "sam", "walk_in", **{"from": "left", "to": 0.5}), A(3, "sam", "fall"), A(7, "sam", "facepalm")], "medium", "none")]},
    "desk_work": {"cast": [("lee", "worker")], "sets": {"set": "office"}, "scenes": [
        ("He sat at the desk and worked and then stood up and left", "set", [A(0, "lee", "sit"), A(4, "lee", "nod"), A(7, "lee", "stand"), A(9, "lee", "walk_out", to_side="right")], "medium", "none")]},
    "presenting": {"cast": [("kim", "boss")], "sets": {"set": "stage"}, "scenes": [
        ("The price is only five dollars and it is the best offer", "set", [A(0, "kim", "hold_sign", bubble="$5"), A(6, "kim", "explain"), A(9, "kim", "react", emotion="happy")], "medium", "push_in")]},
    "push_pull": {"cast": [("ana", "worker")], "sets": {"set": "street"}, "scenes": [
        ("He pushed the car and then pulled it back again", "set", [A(0, "ana", "push", target="car"), A(5, "ana", "pull", target="car"), A(8, "ana", "shake_head")], "wide", "none")]},
    # ---- Phase 13 vocabulary: stories with real cast, places, props passed between people, marks, weather, hiding, a zoom ----
    "fable_fox": {"cast": [{"id": "fox", "role": "animal", "kind": "emoji", "emoji": "1f98a"}, {"id": "crow", "role": "animal", "kind": "emoji", "emoji": "1f426", "style": {"height": "child"}}], "sets": {"set": {"kind": "nature", "props": ["grapes"]}},
        "scenes": [("A hungry fox saw grapes high on a vine and jumped again and again but could not reach them", "set", [A(0, "fox", "appear"), A(1, "fox", "mark", mark="question"), A(4, "fox", "jump"), A(6, "crow", "appear"), A(7, "fox", "jump"), A(10, "fox", "mark", mark="sweat"), A(11, "crow", "laugh")], "medium", "zoom_to", {"focus": "grapes"})]},
    "wallet_story": {"cast": [{"id": "rafi", "role": "friend", "style": {"accessory": "cap", "shirt": "#3b82f6", "hair": "short"}}, {"id": "owner", "role": "elder", "style": {"height": "elder", "accessory": "beard", "shirt": "#b45309", "color": "#374151"}}], "sets": {"set": {"kind": "street", "props": ["wallet"]}},
        "scenes": [("Rafi found a wallet and ran to the shop and gave it back and the old man hugged him", "set", [A(0, "rafi", "walk_in", **{"from": "left", "to": 0.25}), A(2, "rafi", "mark", mark="exclaim"), A(3, "rafi", "lift", prop="wallet"), A(5, "owner", "walk_in", **{"from": "right", "to": 0.78}), A(6, "rafi", "give", prop="wallet", target="owner"), A(11, "owner", "hug", target="rafi")], "wide", "none")]},
    "night_rain": {"cast": [{"id": "mia", "role": "student", "style": {"hair": "long", "shirt": "#a855f7", "height": "child"}}], "sets": {"set": {"kind": "home", "time": "night", "weather": "rain"}},
        "scenes": [("It was a stormy night and she could not sleep so she yawned and looked at her phone", "set", [A(0, "mia", "sit"), A(4, "mia", "yawn"), A(6, "mia", "mark", mark="zzz"), A(9, "mia", "phone")], "medium", "push_in")]},
    "kitchen": {"cast": [{"id": "chef", "role": "cook", "style": {"accessory": "apron", "hair": "short", "shirt": "#f97316"}}], "sets": {"set": "kitchen"},
        "scenes": [("He cooked a big meal and tasted it and laughed because it was so good", "set", [A(0, "chef", "walk_in", **{"from": "left", "to": 0.4}), A(3, "chef", "eat"), A(6, "chef", "laugh"), A(8, "chef", "mark", mark="heart")], "medium", "none")]},
    "haggle": {"cast": [{"id": "buyer", "role": "customer", "style": {"accessory": "scarf", "hair": "bun", "shirt": "#10b981"}}, {"id": "seller", "role": "seller", "style": {"accessory": "hat", "shirt": "#ef4444"}}], "sets": {"set": "shop_inside"},
        "scenes": [("They argued about the price then agreed and shook hands and bowed", "set", [A(0, "buyer", "argue"), A(1, "seller", "argue"), A(3, "seller", "mark", mark="anger"), A(5, "buyer", "walk_to", to=0.4), A(6, "buyer", "handshake", target="seller"), A(9, "seller", "bow")], "medium", "none")]},
    "idea": {"cast": [{"id": "lee", "role": "worker", "style": {"accessory": "glasses", "shirt": "#0ea5e9"}}, {"id": "bulb", "role": "object", "kind": "emoji", "emoji": "1f4a1"}], "sets": {"set": "office"},
        "scenes": [("He typed for hours then suddenly had an idea and cheered", "set", [A(0, "lee", "sit"), A(1, "lee", "type"), A(5, "bulb", "appear"), A(5, "lee", "mark", mark="idea"), A(6, "bulb", "spin"), A(8, "lee", "stand"), A(9, "lee", "celebrate")], "medium", "none")]},
    "island": {"cast": [{"id": "kid", "role": "child", "style": {"height": "child", "accessory": "headband", "shirt": "#facc15"}}, {"id": "gran", "role": "elder", "style": {"height": "elder", "hair": "bun", "shirt": "#14b8a6"}}], "sets": {"set": "island"},
        "scenes": [("The children waved to the boat and threw a ball to their friend", "set", [A(0, "kid", "wave_both"), A(1, "gran", "wave"), A(4, "kid", "throw", prop="ball", target="gran"), A(8, "gran", "clap")], "wide", "pan_right")]},
    "hide_seek": {"cast": [{"id": "tom", "role": "thief", "style": {"accessory": "mask", "shirt": "#475569"}}], "sets": {"set": {"kind": "factory", "props": ["crate"]}},
        "scenes": [("He tiptoed past the machine and hid behind a crate and peeked out afraid", "set", [A(0, "tom", "walk_in", **{"from": "left", "to": 0.2}), A(2, "tom", "sneak", to=0.55), A(6, "tom", "hide", target="crate"), A(8, "tom", "peek"), A(10, "tom", "react", emotion="scared")], "medium", "none")]},
}
SETPROPS = {}


def build_script(name: str, spec: dict) -> tuple[dict, object, object]:
    texts = [s[0] for s in spec["scenes"]]
    tr, beats = make(texts)
    cast = []
    for i, c in enumerate(spec["cast"]):
        if isinstance(c, dict):
            cast.append({"name": c["id"].title(), **c})
        else:
            cid, role = c
            cast.append({"id": cid, "role": role, "name": cid.title(), "style": {"color": "#1f2937" if i == 0 else "#2563eb", "head": "round", "accessory": "none"}})
    sets_by = {}
    for sc in spec["scenes"]:
        k = sc[1]
        v = spec["sets"][k]
        sets_by[k] = v if isinstance(v, dict) else {"kind": v}
    sets = [{"id": k, "props": SETPROPS.get(v["kind"], []), **v} for k, v in sets_by.items()]
    scenes = []
    for i, item in enumerate(spec["scenes"]):
        text, st, acts, shot, move = item[:5]
        extra = item[5] if len(item) > 5 else {}
        ids = beats.beats[i].word_ids
        actions = []
        for a in acts:
            d = {kk: vv for kk, vv in a.items() if kk != "k"}
            d["at_word"] = ids[min(a["k"], len(ids) - 1)]
            actions.append(d)
        scenes.append({"id": f"s{i + 1}", "beats": [beats.beats[i].id], "set": st, "camera": {"shot": shot, "move": move, **extra}, "transition_in": "cut" if i == 0 else "fade", "actions": actions, "overlays": []})
    script = {"version": "1.0", "kind": "stick", "meta": {"language": "en", "audience": "everyone", "tone": "warm", "aspect": "9:16"}, "cast": cast, "sets": sets, "scenes": scenes}
    return script, tr, beats


def figure_mask(im: np.ndarray) -> np.ndarray:
    """Pixels that are drawn (not the page): whatever differs from the background colour taken from the corners, so a night scene works as well as a day one."""
    corners = np.concatenate([im[:10, :10].reshape(-1, 3), im[:10, -10:].reshape(-1, 3), im[-10:, :10].reshape(-1, 3), im[-10:, -10:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    return np.abs(im.astype("int16") - bg).sum(axis=2) > 120


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aspects", default="9:16,16:9")
    ap.add_argument("--out", default=str(ROOT / "qa_out_stick"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = [n for n in PATTERNS if not a.only or n in a.only.split(",")]
    theme = load_theme("paper")
    icons = all_icon_names()
    problems: list[str] = []
    for aspect in a.aspects.split(","):
        sheets: list[Path] = []
        for name in names:
            script, tr, beats = build_script(name, PATTERNS[name])
            script = repair_script(script, tr, beats, "stick")
            errs = validate_script(script, tr, beats, icons)
            if errs:
                problems.append(f"{name}: the script does not validate: {errs[:3]}")
                continue
            from vt.script.models import VideoScript

            sf = compile_script(VideoScript.model_validate(script), tr, beats, theme.name)
            t0, t1 = beats.beats[0].start, beats.beats[-1].end + 0.6
            dur = round(t1 + 0.4, 2)
            envelope = {"dt": 0.04, "v": [0.5] * int(dur / 0.04)}
            data = resolve_composition(sf, tr, beats, theme, aspect, dur, None, media={}, envelope=envelope, language="en")
            data["icons"] = {}
            d = out / f"{name}-{aspect.replace(':', 'x')}"
            idx = write_composition(d / "comp", data, theme)
            times = [round(t0 + (t1 - t0) * f, 2) for f in (0.08, 0.35, 0.62, 0.92)]
            frames = snapshot(idx.parent, d / "snap", times)
            if len(frames) != 4:
                problems.append(f"{name} {aspect}: {len(frames)} frames instead of 4")
                continue
            ims = [np.asarray(Image.open(f).convert("RGB")) for f in frames]
            h = ims[0].shape[0]
            stage = [im[: int(h * 0.74)] for im in ims]
            ink = [float(figure_mask(s).mean()) for s in stage]
            diffs = [float(np.abs(stage[i].astype("int16") - stage[i + 1].astype("int16")).mean()) for i in range(3)]
            xs = [float(np.nonzero(figure_mask(st))[1].mean() / st.shape[1]) if figure_mask(st).any() else 0.5 for st in stage]
            centre = float(np.mean(xs))
            print(f"{name:12} {aspect:5} ink {[round(v, 3) for v in ink]} change {[round(v, 1) for v in diffs]} centre {centre:.2f}")
            if min(ink) < 0.004:
                problems.append(f"{name} {aspect}: the figure is (almost) invisible in a frame (ink {min(ink):.4f})")
            if max(diffs) < 0.8 or sum(1 for v in diffs if v > 0.3) < 2:
                problems.append(f"{name} {aspect}: the picture hardly changes between frames {diffs}")
            if not 0.30 <= centre <= 0.70:
                problems.append(f"{name} {aspect}: the drawing sits to one side (its centre of ink is at {centre:.2f} of the width)")
            w, hh = (270, 480) if aspect == "9:16" else (480, 270)
            sheet = Image.new("RGB", (w * 4, hh), "white")
            for i, f in enumerate(frames):
                sheet.paste(Image.open(f).convert("RGB").resize((w, hh)), (i * w, 0))
            sp = d / "sheet.png"
            sheet.save(sp)
            sheets.append(sp)
        if sheets:
            rows = [Image.open(s) for s in sheets]
            big = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), "white")
            y = 0
            for r in rows:
                big.paste(r, (0, y))
                y += r.height
            big.save(out / f"all-{aspect.replace(':', 'x')}.png")
    print("no problems found" if not problems else "\n".join("PROBLEM: " + p for p in problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
