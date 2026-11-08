"""Looks at what the stick-figure director really makes: for sample transcripts it builds the plan with the rules director and with the AI director (the owner's local model),
prints a storyboard a person can read, and measures how varied it is (characters, places, different verbs, props, overlay kinds, longest time with nothing new, how much of the video
is one figure talking). This is the check for "no creative intelligence": numbers alone are not enough, read the storyboard.

    python scripts/qa_director.py [--sets story-wallet,edu-money] [--engine rules|ai|both] [--ollama http://192.168.123.47:11434] [--model gemma4:latest]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests" / "script_eval"))
from transcripts import SETS  # noqa: E402

from vt import ai, llm  # noqa: E402
from vt.planner import plan_rules  # noqa: E402
from vt.script import examples as EX  # noqa: E402
from vt.script.models import VideoScript  # noqa: E402
from vt.script.rules_stick import rules_script  # noqa: E402
from vt.script.validate import validate_script  # noqa: E402


def stats(script: VideoScript, tr, beats) -> dict:
    words = tr.by_id()
    verbs = Counter(a.do for sc in script.scenes for a in sc.actions)
    props = {p for s in script.sets for p in s.props} | {a.prop for sc in script.scenes for a in sc.actions if getattr(a, "prop", None)}
    over = Counter(o.get("type") for sc in script.scenes for o in sc.overlays)
    pts = sorted([words[a.at_word].start for sc in script.scenes for a in sc.actions if a.at_word in words] + [words[o["at_word"]].start for sc in script.scenes for o in sc.overlays if o.get("at_word") in words]
                 + [b.start for sc in script.scenes for b in beats.beats if b.id == sc.beats[0]])
    t0, t1 = beats.beats[0].start, beats.beats[-1].end
    gaps = [b - a for a, b in zip([t0] + pts, pts + [t1])]
    n_act = sum(verbs.values()) or 1
    talk = sum(v for k, v in verbs.items() if k in ("say", "explain", "idle", "nod"))
    who = Counter(a.who for sc in script.scenes for a in sc.actions)
    return {"characters": len(script.cast), "speaking": len(who), "sets": len({sc.set for sc in script.scenes}), "set_kinds": len({s.kind for s in script.sets}), "verbs": len(verbs),
            "props": len(props), "overlay_kinds": len(over), "max_gap_s": round(max(gaps), 1), "talk_share": round(talk / n_act, 2), "top_verb_share": round(verbs.most_common(1)[0][1] / n_act, 2) if verbs else 0,
            "camera_moves": len({sc.camera.move for sc in script.scenes}), "transitions": len({sc.transition_in for sc in script.scenes})}


def story(script: VideoScript, tr, beats) -> str:
    words = tr.by_id()
    sets = {s.id: s.kind for s in script.sets}
    lines = [f"  cast: " + ", ".join(f"{c.name} ({c.role})" for c in script.cast) + "   sets: " + ", ".join(f"{s.id}={s.kind}[{','.join(s.props)}]" for s in script.sets)]
    for sc in script.scenes:
        text = " ".join(b.text for b in beats.beats if b.id in sc.beats)
        acts = ", ".join(f"{a.who}:{a.do}" + (f"({a.target or a.prop or a.bubble or ''})" if (a.target or a.prop or a.bubble) else "") for a in sc.actions)
        ov = ", ".join(o.get("type", "?") for o in sc.overlays)
        lines.append(f"  {sc.id} [{sets.get(sc.set, sc.set)}, {sc.camera.shot}/{sc.camera.move}, in:{sc.transition_in}] \"{text[:60]}\"\n      acts: {acts or '-'}   overlays: {ov or '-'}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="story-wallet,edu-money,product-app")
    ap.add_argument("--engine", default="both")
    ap.add_argument("--ollama", default="http://192.168.123.47:11434")
    ap.add_argument("--model", default="")
    ap.add_argument("--out", default=str(ROOT / "qa_out_director"))
    a = ap.parse_args()
    llm.settings = lambda: {"llm_mode": "auto", "ollama_url": a.ollama, "ollama_model": a.model, "llm_auto_download": False}      # type: ignore[assignment]
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    if a.engine in ("ai", "both") and not llm.reachable():
        print("no AI server reachable at", a.ollama)
        return 2
    from vt.script.planner import ai_script

    for name in a.sets.split(","):
        tr, beats = EX.make(SETS[name])
        lang = "bn" if name.startswith("bn") else "en"
        sf = plan_rules(tr, beats, "paper", language=lang)
        print(f"\n===== {name}: {len(beats.beats)} sentences, {beats.beats[-1].end:.0f} s")
        for eng in (["rules", "ai"] if a.engine == "both" else [a.engine]):
            try:
                s = rules_script(tr, beats, sf, kind="stick", language=lang) if eng == "rules" else ai_script(tr, beats, kind="stick", language=lang, draft=sf)
            except ai.AIUnavailable as e:
                print(f"--- {eng}: FAILED {str(e)[:200]}")
                continue
            errs = validate_script(s.model_dump(by_alias=True), tr, beats)
            print(f"--- {eng} (valid: {not errs}) {json.dumps(stats(s, tr, beats))}")
            print(story(s, tr, beats))
            (out / f"{name}-{eng}.json").write_text(s.model_dump_json(by_alias=True, exclude_none=True, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
