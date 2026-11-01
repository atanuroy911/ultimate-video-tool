"""The editor's critic: reads a Video Script the way a picky editor watches a cut, and says scene by scene what is dull.

`score.py` checks that a script is *correct* (valid, covers every sentence, keeps numbers). This checks that it is *interesting*,
with the targets of the plan (old P13.5): something new at least every MAX_STILL s (the owner's 3-second rule, with margin),
at most TALK_SHARE of the actions plain talking, no actor doing the same thing twice in a row, the cast and places that were
planned actually used, enough different verbs and camera moves for the length, overlays that do not repeat one kind three
times running. Every issue names a scene, says what is wrong in plain words and what would fix it, so the same list can go to
an AI ("revise these scenes") or to the deterministic enricher, and be shown to the person.
"""
from __future__ import annotations

from ..schema import Beats, Transcript
from .models import Action, VideoScript

MAX_STILL = 2.8
TALK_SHARE = 0.30
TALK = {"explain", "say", "nod", "idle", "stand"}
VERBS_PER_10 = 8


def _events(s: VideoScript, tr: Transcript, beats: Beats) -> dict[str, list[float]]:
    """Scene id -> times (s) where something new appears: the scene start, every action, overlay and sound cue."""
    w = tr.by_id()
    bstart = {b.id: b.start for b in beats.beats}
    out = {}
    for sc in s.scenes:
        t = [bstart.get(sc.beats[0], 0.0)]
        t += [w[a.at_word].start for a in sc.actions if a.at_word in w]
        t += [w[o["at_word"]].start for o in sc.overlays if o.get("at_word") in w]
        t += [w[c.at_word].start for c in sc.sfx if c.at_word in w]
        out[sc.id] = sorted(t)
    return out


def review(script: VideoScript | dict, tr: Transcript, beats: Beats) -> dict:
    """{score 0-100, metrics, issues: [{scene, problem, fix}]}. Higher is better; an empty issue list means nothing to fix."""
    s = script if isinstance(script, VideoScript) else VideoScript.model_validate(script)
    bend = {b.id: b.end for b in beats.beats}
    btext = {b.id: b.text for b in beats.beats}
    ev = _events(s, tr, beats)
    issues: list[dict] = []
    longest = 0.0
    for sc in s.scenes:
        end = bend.get(sc.beats[-1], ev[sc.id][-1])
        pts = ev[sc.id] + [end]
        gap, at = max(((b - a, a) for a, b in zip(pts, pts[1:])), default=(0.0, 0.0))
        longest = max(longest, gap)
        if gap > MAX_STILL:
            issues.append({"scene": sc.id, "problem": f"nothing new for {gap:.1f} s (from {at:.1f} s)", "fix": "add an action, a graphic or a camera move in that stretch"})
        last: dict[str, str] = {}
        for a in sc.actions:
            if last.get(a.who) == a.do and a.do not in ("walk_to",):
                issues.append({"scene": sc.id, "problem": f"{a.who} does '{a.do}' twice in a row", "fix": "give the second one a different verb that fits the words"})
                break
            last[a.who] = a.do
        if sc.actions and all(a.do in TALK for a in sc.actions) and len(sc.actions) >= 2:
            issues.append({"scene": sc.id, "problem": "only talking: " + " / ".join(btext.get(b, "")[:40] for b in sc.beats[:1]), "fix": "act out what is said (a prop, a reaction, a movement, a sign)"})
    types = [o.get("type") for sc in s.scenes for o in sc.overlays]
    for i in range(2, len(types)):
        if types[i] and types[i] == types[i - 1] == types[i - 2]:
            sc = next(sc for sc in s.scenes if any(o.get("type") == types[i] for o in sc.overlays))
            issues.append({"scene": sc.id, "problem": f"the same graphic ({types[i]}) three times running", "fix": "use another kind of graphic for one of them"})
            break
    acts = [a for sc in s.scenes for a in sc.actions]
    talk = sum(a.do in TALK for a in acts) / len(acts) if acts else 0.0
    verbs = len({a.do for a in acts})
    n10 = max(1.0, len(beats.beats) / 10)
    used_cast = {a.who for a in acts}
    used_sets = {sc.set for sc in s.scenes if sc.set}
    moves = sum(sc.camera.move != "none" for sc in s.scenes)
    props = len({a.prop for a in acts if a.prop})
    if s.kind in ("stick", "cartoon"):
        if acts and talk > TALK_SHARE:
            issues.append({"scene": s.scenes[0].id, "problem": f"{round(talk * 100)} % of the actions are plain talking", "fix": f"at most {round(TALK_SHARE * 100)} %: show, do not tell"})
        if verbs < VERBS_PER_10 * min(1.0, n10):
            issues.append({"scene": s.scenes[0].id, "problem": f"only {verbs} different actions", "fix": f"aim for {VERBS_PER_10} or more different verbs per 10 sentences"})
        unused = [c.name or c.id for c in s.cast if c.id not in used_cast]
        if unused:
            issues.append({"scene": s.scenes[0].id, "problem": "cast never on screen: " + ", ".join(unused), "fix": "bring them in where the story mentions them, or drop them"})
        if len(s.scenes) >= 4 and moves < 2:
            issues.append({"scene": s.scenes[len(s.scenes) // 2].id, "problem": "the camera never moves", "fix": "a push-in at a key moment, a pan when someone walks"})
    metrics = {"longest_still_s": round(longest, 2), "talk_share": round(talk, 2), "verbs": verbs, "cast_used": len(used_cast), "cast": len(s.cast),
               "places": len(used_sets), "camera_moves": moves, "props": props, "issues": len(issues)}
    score = 100 - min(60, 12 * sum(1 for i in issues if "nothing new" in i["problem"])) - 6 * sum(1 for i in issues if "nothing new" not in i["problem"])
    return {"score": max(0, score), "metrics": metrics, "issues": issues}


# --------------------------------------------------------------------------- the deterministic enricher
REACT = ["think", "react", "shrug", "clap", "laugh", "look_at", "point", "jump", "wave_both", "facepalm", "celebrate", "bow"]


def enrich(script: VideoScript, tr: Transcript, beats: Beats) -> tuple[VideoScript, int]:
    """Fill every still stretch longer than MAX_STILL in a scene that has actors: at the spoken word nearest the middle of the gap, the
    actor of the scene does something it has not just done, chosen from verbs that need no extra field (a reaction, a gesture), and a
    question gets "think", a number gets "count", an exclamation "react". Never touches words, timing or the AI's own choices.
    Returns (script, actions added). What no actor can fill is left to the composer's heartbeat (vt/director/heartbeat.py)."""
    from . import catalogue as C

    s = script.model_copy(deep=True)
    words = [w for w in tr.words if not w.cut]
    by_beat = {b.id: b for b in beats.beats}
    ok = [v for v in REACT if v in C.VERBS and not C.VERBS[v][2]]
    added = 0
    for sc in s.scenes:
        actors = [a.who for a in sc.actions] or ([s.cast[0].id] if s.cast and s.kind in ("stick", "cartoon") else [])
        if not actors:
            continue
        who = max(set(actors), key=actors.count)
        for _ in range(6):                                   # a long scene can need more than one
            ev = _events(s, tr, beats)[sc.id] + [by_beat[sc.beats[-1]].end if sc.beats[-1] in by_beat else 0.0]
            gap, a, b = max(((y - x, x, y) for x, y in zip(ev, ev[1:])), default=(0.0, 0.0, 0.0))
            if gap <= MAX_STILL:
                break
            mid = (a + b) / 2
            inside = [w for w in words if a + 0.4 < w.start < b - 0.4]
            if not inside:
                break
            cue = [x for x in inside if x.text.strip().endswith(("?", "!")) or any(ch.isdigit() for ch in x.text)]      # react to the words when they give a reason
            w = min(cue or inside, key=lambda x: abs(x.start - mid))
            prev = [x.do for x in sc.actions if x.who == who]
            text = w.text.strip()
            digits = "".join(ch for ch in text if ch.isdigit())
            extra: dict = {}
            if text.endswith("?"):
                want = "think"                                       # a question: the actor wonders
            elif digits and 1 <= int(digits) <= 5:
                want, extra = "count", {"count": int(digits)}        # a small number: counted on fingers
            elif digits or text.endswith("!"):
                want = "react"                                       # a big number or an exclamation: surprise
            else:
                want = None
            neutral = [v for v in ok if v != "think"]               # "think" is kept for questions
            if want and want in C.VERBS and (not prev or prev[-1] != want):
                verb = want
            else:
                extra = {}
                verb = next((v for v in neutral if not prev or (v != prev[-1] and v not in prev[-2:])), None)
            if verb is None:
                break
            sc.actions.append(Action.model_validate({"at_word": w.id, "who": who, "do": verb, **extra}))
            sc.actions.sort(key=lambda x: next((ww.start for ww in words if ww.id == x.at_word), 0.0))
            added += 1
    return s, added
