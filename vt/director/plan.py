"""The director: transcript -> a complete, varied scene plan for the chosen use case, with rules only (no AI needed).

    beats -> facts and roles -> groups (scenes) -> media assignment -> archetype per scene -> elements, layout, transition, backdrop

Everything is seeded by the project id, so the same input always gives the same video, and different projects differ.
"""
from __future__ import annotations

import random
import re
from typing import Callable, Optional

from ..schema import Backdrop, Beats, MediaItem, Scene, Scrim, ScenesFile, Transcript
from ..stages.words import norm_token
from . import archetypes as A
from . import profiles as P
from . import roles as R


def make_groups(facts: list[R.Facts], profile: dict) -> list[A.Group]:
    """Cut the sentences into scenes: by pace, and at sentences that deserve a scene of their own (questions, definitions, calls to action)."""
    pace = profile["pace"]
    lo, target, hi = pace["scene_min"], pace["scene_target"], pace["scene_max"]
    groups: list[list[R.Facts]] = []
    cur: list[R.Facts] = []
    for f in facts:
        if cur:
            d = cur[-1].beat.end - cur[0].beat.start
            prev = cur[-1]
            steps_run = f.role == "step" and prev.role == "step"
            cap = hi * (1.8 if steps_run else 1.0)
            boundary = False
            if f.speaker and prev.speaker and f.speaker != prev.speaker:
                boundary = True
            elif f.role in ("question", "definition", "cta", "price") and d >= lo * 0.55:
                boundary = True
            elif prev.role in ("question", "definition", "cta") and d >= lo * 0.55:
                boundary = True
            elif f.role == "quote" and d >= lo * 0.55:
                boundary = True
            elif steps_run:
                boundary = d + f.dur > cap
            elif d >= target or d + f.dur > hi:
                boundary = True
            if boundary:
                groups.append(cur)
                cur = []
        cur.append(f)
    if cur:
        groups.append(cur)
    # a very short tail joins the scene before it (unless the speaker changes)
    merged: list[list[R.Facts]] = []
    for g in groups:
        d = g[-1].beat.end - g[0].beat.start
        if merged and d < lo * 0.7:
            pd = merged[-1][-1].beat.end - merged[-1][0].beat.start
            if pd + d <= hi * 1.3 and merged[-1][-1].speaker == g[0].speaker and g[0].role not in ("cta", "definition"):
                merged[-1].extend(g)
                continue
        merged.append(g)
    return [A.Group(facts=g) for g in merged]


def assign_media(groups: list[A.Group], media: list[MediaItem]) -> None:
    """Give each picture/clip the sentences it belongs to: by words in its caption/tags/name, then spread the rest evenly."""
    if not media or not groups:
        return
    word_sets = [{norm_token(w.text) for w in g.words} for g in groups]
    taken: set[int] = set()
    left: list[MediaItem] = []
    for m in media:
        toks = {t for t in re.findall(r"\w+", f"{m.caption} {' '.join(m.tags)} {m.id.replace('-', ' ')}".lower()) if len(t) > 2}
        scored = [(len(toks & word_sets[i]), -i) for i in range(len(groups)) if i not in taken]
        best = max(scored) if scored else None
        if best and best[0] >= 1:
            i = -best[1]
        else:
            left.append(m)
            continue
        groups[i].media_id, groups[i].media_kind, groups[i].media_ratio = m.id, ("video" if m.kind in ("video", "gif") else "image"), (m.width / m.height if m.height else 1.0)
        taken.add(i)
    eligible = [i for i, g in enumerate(groups) if i not in taken and not (g.roles & {"definition", "question"})]
    if left and eligible:
        step = len(eligible) / len(left)
        for k, m in enumerate(left):
            i = eligible[min(len(eligible) - 1, int(k * step + step / 2))]
            while i in taken and i + 1 < len(groups):
                i += 1
            groups[i].media_id, groups[i].media_kind, groups[i].media_ratio = m.id, ("video" if m.kind in ("video", "gif") else "image"), (m.width / m.height if m.height else 1.0)
            taken.add(i)


def choose(g: A.Group, ctx: A.Ctx, recent: list[A.Archetype], rng: random.Random) -> list[tuple[float, A.Archetype]]:
    """All archetypes that can show this group, best first."""
    last = recent[-1] if recent else None
    big_recently = any(a.big for a in recent[-3:])
    scored = []
    for a in A.ARCHETYPES.values():
        if g.media_id and a.family != "media":                 # a picture the user gave (or matched by caption) must actually appear in its scene
            continue
        fit = a.fit(g, ctx)
        w = P.weight(ctx.profile, a.name)
        if fit <= 0 or w <= 0:
            continue
        s = fit * w
        if a.repeat_ok:
            pass
        elif last and a.name == last.name:
            s *= 0.1
        elif last and a.family == last.family and a.family not in ("picture",):
            s *= 0.5
        elif any(a.name == r.name for r in recent[-3:]):
            s *= 0.65
        if a.big and not big_recently:
            s *= 1.4
        s *= 0.9 + 0.2 * rng.random()
        scored.append((s, a))
    scored.sort(key=lambda t: -t[0])
    return scored


def plan(tr: Transcript, beats: Beats, *, theme: str = "paper", language: str = "bn", usecase: str = "general", picks: Optional[dict] = None,
         media: Optional[list[MediaItem]] = None, seed: str = "vt", brief: Optional[dict] = None, aspect: str = "9:16",
         scrim_fn: Optional[Callable[..., Scrim]] = None) -> ScenesFile:
    profile = P.get(usecase if usecase in P.USECASES[1:] else "general")
    facts = R.analyse(tr, beats, language)
    groups = make_groups(facts, profile)
    assign_media(groups, media or [])
    rng = random.Random(f"{seed}|{usecase}")
    ctx = A.Ctx(words=tr.by_id(), language=language, picks=picks or {}, profile=profile, usecase=usecase if usecase != "auto" else "general", brief=brief or {}, rng=rng,
                media={m.id: m for m in (media or [])}, aspect=aspect)
    media_by_id = {m.id: m for m in (media or [])}
    scenes: list[dict] = []
    recent: list[A.Archetype] = []
    from collections import Counter as _C

    _vis = _C(p.sticker for p in (picks or {}).values() if getattr(p, "sticker", None))
    topic_visual = _vis.most_common(1)[0][0] if _vis and _vis.most_common(1)[0][1] >= 2 else None    # what the video keeps showing (a black hole)
    trans = profile.get("transitions") or ["fade"]
    last_trans = ""
    for si, g in enumerate(groups):
        built = None
        for score, arch in choose(g, ctx, recent, rng):
            out = arch.build(g, ctx)
            if out and out[0]:
                built = (arch, out)
                break
        if not built:                       # nothing fits: the scene's key term as typography, else the video's own topic picture again
            kw = A._keyword(g.words, A._topics(ctx))
            if kw:
                els = [{"type": "keyword", "text": A.clip(kw.text, 30), "style": "underline", "at_word": kw.id}]
            elif topic_visual:
                els = [{"type": "sticker", "emoji": topic_visual, "label": "", "at_word": g.first_word().id}]
            else:                           # the gist of the sentence in big type ("remember to invest"), when it reads well on its own
                from .phrases import tidy

                gist = tidy(g.facts[-1].text, 30, min_content=2)
                els = [{"type": "keyword", "text": gist, "style": "underline", "at_word": g.facts[-1].words[0].id}] if gist else []
            built = (A.ARCHETYPES["picture"], (els, {"highlight": kw.id} if kw else {}))
        arch, (els, extra) = built
        place = next((f.place for f in reversed(g.facts) if f.place), None)
        if place:                                  # the story moved on, even if this scene is not a cartoon: the next cartoon starts where we are now
            ctx.last_set = place
        if arch.name in ("picture", "cartoon", "media_frame"):
            ctx.pattern += 1
        recent.append(arch)
        layout = extra.get("layout", "stack")
        sc: dict = {"id": f"s{si + 1}", "beats": g.beats, "layout": layout, "elements": els[:5], "tone": si % 4,
                    "archetype": arch.name, "role": g.role, "caption": {"highlight_words": [extra["highlight"]] if extra.get("highlight") else []}}
        if si == 0:
            sc["transition_in"] = "cut"
        elif g.facts[0].speaker and scenes and scenes[-1].get("_speaker") != g.facts[0].speaker:
            sc["transition_in"] = "cut"
        else:
            options = [t for t in trans if t != last_trans] or trans
            sc["transition_in"] = rng.choice(options)
        last_trans = sc["transition_in"]
        sc["_speaker"] = g.facts[0].speaker
        if extra.get("backdrop"):
            bd = dict(extra["backdrop"])
            m = media_by_id.get(bd["media"])
            if m:
                bd["fx"], bd["fy"] = m.fx, m.fy
            if scrim_fn:
                bd["scrim"] = scrim_fn(bd["media"], aspect, layout, g.start, g.end).model_dump()
            sc["backdrop"] = bd
        scenes.append(sc)
    for sc in scenes:
        sc.pop("_speaker", None)
    return ScenesFile.model_validate({"theme": theme, "planner": "rules", "scenes": scenes})


USECASE_SIGNALS = {
    "product": {"cta": 1.2, "price": 1.5, "feature": 1.3, "proof": 1.2, "problem": 0.5},
    "story": {"story": 1.0, "quote": 0.6},
    "education": {"definition": 1.6, "explain": 0.9, "step": 1.0, "question": 0.8, "recap": 1.0, "date": 0.5, "list": 0.4},
    "discussion": {"contrast": 0.8, "question": 0.5, "quote": 0.3},
}


def detect_usecase(facts: list[R.Facts], has_media: bool = False) -> str:
    """Which kind of video is this? Counted from the roles of its sentences (a few cues are enough); 'general' when nothing stands out."""
    if not facts:
        return "general"
    speakers = {f.speaker for f in facts if f.speaker}
    if len(speakers) >= 2:
        return "discussion"
    score = {k: 0.0 for k in USECASE_SIGNALS}
    for f in facts:
        for uc, sig in USECASE_SIGNALS.items():
            score[uc] += sum(w for r, w in sig.items() if r in f.roles)
    n = len(facts)
    if has_media:
        score["product"] += 0.3 * min(3, n)
    best = max(score, key=score.get)
    return best if score[best] >= max(1.5, n * 0.2) else "general"


ARCHETYPE_LABELS = {
    "title_card": "Title", "hero_number": "Big number", "ring": "Percentage ring", "stat_row": "Key figures", "bar_compare": "Bars / compare", "line_trend": "Trend line",
    "timeline": "Timeline", "steps": "Steps", "checklist": "Checklist", "definition": "Definition", "question": "Question", "pros_cons": "Pros and cons",
    "quote_card": "Quote", "cartoon": "Cartoon scene", "feature_grid": "Feature cards", "price_cta": "Price / call to action", "device": "Device mockup",
    "flow": "Flowchart", "cycle": "Cycle", "hierarchy": "Tree", "venn": "Venn diagram", "funnel": "Funnel", "pyramid": "Pyramid", "matrix": "2 x 2 matrix",
    "pictogram": "Figures (x out of y)", "gauge": "Gauge", "media_hero": "Full-screen picture", "media_frame": "Framed picture", "speaker": "Speaker card", "picture": "Pictures and keywords",
}


def _scene_context(tr: Transcript, beats: Beats, scene: Scene, *, language: str, usecase: str, picks, media, brief, seed: str, media_id: Optional[str] = None, aspect: str = "9:16"):
    facts = R.analyse(tr, beats, language)
    by = {f.beat.id: f for f in facts}
    g = A.Group(facts=[by[b] for b in scene.beats if b in by])
    mid = media_id or (scene.backdrop.media if scene.backdrop else next((getattr(e, "media", None) for e in scene.elements if getattr(e, "media", None)), None))
    m = next((x for x in (media or []) if x.id == mid), None)
    if m:
        g.media_id, g.media_kind, g.media_ratio = m.id, ("video" if m.kind in ("video", "gif") else "image"), (m.width / m.height if m.height else 1.0)
    ctx = A.Ctx(words=tr.by_id(), language=language, picks=picks or {}, profile=P.get(usecase), usecase=usecase if usecase != "auto" else "general", brief=brief or {},
                rng=random.Random(f"{seed}|{scene.id}"), media={m.id: m for m in (media or [])}, aspect=aspect)
    return g, ctx


def options_for_scene(tr: Transcript, beats: Beats, scene: Scene, *, language: str = "bn", usecase: str = "general", picks=None, media=None, brief=None, seed: str = "vt") -> list[dict]:
    """The scene types this scene's sentences can be shown as, best fit first (what the Studio offers under 'Show as')."""
    g, ctx = _scene_context(tr, beats, scene, language=language, usecase=usecase, picks=picks, media=media, brief=brief, seed=seed)
    out = []
    for a in A.ARCHETYPES.values():
        if a.family == "media" and not g.media_id:
            continue
        fit = a.fit(g, ctx)
        if fit > 0 and a.build(g, ctx):
            out.append({"id": a.name, "label": ARCHETYPE_LABELS.get(a.name, a.name), "fit": round(fit, 2), "current": a.name == scene.archetype})
    return sorted(out, key=lambda o: -o["fit"])


def reshow(tr: Transcript, beats: Beats, scene: Scene, archetype: str, *, language: str = "bn", usecase: str = "general", picks=None, media=None, brief=None,
           seed: str = "vt", aspect: str = "9:16", scrim_fn: Optional[Callable[..., Scrim]] = None, media_id: Optional[str] = None) -> Scene:
    """The same sentences, shown as another scene type. Raises ValueError (with a plain reason) when the sentences do not contain what that type needs."""
    if archetype not in A.ARCHETYPES:
        raise ValueError(f"unknown scene type '{archetype}'")
    if media_id and not any(m.id == media_id for m in (media or [])):
        raise ValueError(f"'{media_id}' is not in the media bin")
    g, ctx = _scene_context(tr, beats, scene, language=language, usecase=usecase, picks=picks, media=media, brief=brief, seed=seed, media_id=media_id, aspect=aspect)
    a = A.ARCHETYPES[archetype]
    if a.family == "media" and not g.media_id:
        raise ValueError("this scene has no picture or clip yet: add one to the media bin first")
    built = a.build(g, ctx)
    if not built or not built[0]:
        raise ValueError(f"these sentences do not contain what '{ARCHETYPE_LABELS.get(archetype, archetype)}' needs (for example numbers, a list or a person)")
    els, extra = built
    data = scene.model_dump(exclude_none=True)
    data.update({"elements": els[:5], "layout": extra.get("layout", "stack"), "archetype": archetype})
    data.pop("backdrop", None)
    if extra.get("highlight"):
        data["caption"] = {"highlight_words": [extra["highlight"]]}
    if extra.get("backdrop"):
        bd = dict(extra["backdrop"])
        m = next((x for x in (media or []) if x.id == bd["media"]), None)
        if m:
            bd["fx"], bd["fy"] = m.fx, m.fy
        if scrim_fn:
            bd["scrim"] = scrim_fn(bd["media"], aspect, data["layout"], g.start, g.end).model_dump()
        data["backdrop"] = bd
    return Scene.model_validate(data)
