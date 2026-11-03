"""Motion graphics, automatically: the shot recipes of video-shotcraft (124 cards) chosen for every element and scene.

The recipes are implemented in renderer/runtime/vt-motion.js. Here the composition gets, deterministically from the project:
* every text or picture element an entrance (`fx`) that fits what it is: a number counts up, a question glitches, a quote types out,
  a title assembles, a sticker lands with a wave... never the same entrance twice in a row;
* every scene after the first a transition (`tx`) from the transition recipes, punchier in the opening seconds, never the same as
  either of the two before, with some scenes left on the plain cut/fade so the rhythm breathes;
* scene moves (`moves`): an opening on the first scene, an outro on the last, a camera move every few scenes (not on stick-figure
  scenes, which have their own camera) and now and then a rhythm hit.
`CARDS` maps each of the 124 cards to the recipe that realises it (a card made for a product UI uses the mechanism it is built on),
so no card is silently missing; tests/test_motion.py checks that every card in the shotcraft index is mapped to a recipe that exists.
"""
from __future__ import annotations

import hashlib
import re

TEXT = "text"
TRANS = "trans"
SCENE = "scene"

# card -> (registry, recipe). Same-named entries are direct ports; the rest borrow the mechanism they are built on.
CARDS: dict[str, tuple[str, str]] = {
    # camera
    "basic-3d-scene": (SCENE, "steep-tilt-glide"), "crash-zoom-punch": (SCENE, "crash-zoom-punch"), "cursor-flyover": (SCENE, "depth-layer-moves"),
    "depth-layer-moves": (SCENE, "depth-layer-moves"), "graze-face-tour": (SCENE, "steep-tilt-glide"), "overhead-camera-moves": (SCENE, "crane-rise-reveal"),
    "space-camera-moves": (SCENE, "depth-layer-moves"), "steep-tilt-glide": (SCENE, "steep-tilt-glide"), "tension-camera-moves": (SCENE, "tension-camera-moves"),
    "terminal-3d": (SCENE, "steep-tilt-glide"),
    # data (the charts themselves are the infographic elements; these add the number and the reveal)
    "before-after-slider-scrub": (TRANS, "wipe-transitions"), "chart-live-moves": (TEXT, "countdown-arc-scatter"), "gauge-readout-moves": (TEXT, "countdown-arc-scatter"),
    "scroll-brake-moves": (TEXT, "pill-slot-cycle"), "timeline-travel": (TRANS, "transition-travel"),
    # effects
    "assemble-then-type-flyin": (TEXT, "type-assembly-moves"), "aurora-bloom-bg-flip": (TRANS, "gradient-transition"), "brand-frame-snap": (TEXT, "scan-bracket-sweep"),
    "fui-hud-moves": (TEXT, "scan-bracket-sweep"), "glow-flyline-moves": (TEXT, "glow-flyline-moves"), "icon-performance-moves": (TEXT, "element-body-moves"),
    "impact-feedback": (TEXT, "impact-feedback"), "light-play-moves": (TEXT, "spotlight-sweep-moves"), "radial-ripple-phone-chips": (TEXT, "radial-wave"),
    "riso-print-hits": (TEXT, "riso-print-hits"), "scan-bracket-sweep": (TEXT, "scan-bracket-sweep"), "scanline-annotate-focus": (TEXT, "scan-bracket-sweep"),
    "scanline-assemble-flyin": (TEXT, "type-assembly-moves"), "slam-entrance-moves": (TEXT, "slam-entrance-moves"), "spotlight-sweep-moves": (TEXT, "spotlight-sweep-moves"),
    # interaction (app-UI cards: their motion mechanism)
    "autolayout-gap-dial": (TEXT, "brace-expand"), "canvas-materialize-moves": (TEXT, "letterspace-materialize"), "chip-grid-single-select-blackout": (TEXT, "pill-slot-cycle"),
    "collab-cursor-moves": (TEXT, "deck-deal-flyin"), "glass-pill-dictation-typing": (TEXT, "typewriter-moves"), "hashtag-to-pill-materialize": (TEXT, "pill-slot-cycle"),
    "picker-carousel-feature-cycle": (TEXT, "vertical-word-roll-blur-cycle"), "segmented-thumb-hero": (TEXT, "card-flip-reveal"), "theme-switch-moves": (TRANS, "circle-match-iris"),
    "type-and-filter": (TEXT, "typewriter-moves"), "voice-waveform-live": (TEXT, "type-rhythm-sync"),
    # opening
    "brand-ink-open": (SCENE, "brand-ink-open"), "crane-rise-reveal": (SCENE, "crane-rise-reveal"), "dataviz-landscape-open": (SCENE, "crane-rise-reveal"),
    "fracture": (SCENE, "fracture"), "icon-field-colorize": (SCENE, "spotlight-hero-card"), "letterspace-materialize": (TEXT, "letterspace-materialize"),
    "magician-card-flourish": (TEXT, "card-flip-reveal"), "orbit-ring-title-open": (SCENE, "orbit-ring-title-open"), "spotlight-hero-card": (SCENE, "spotlight-hero-card"),
    "stroke-segment-build": (TEXT, "marker-underline-title"), "text-as-mask": (TEXT, "text-as-mask"),
    # outro
    "grain-dissolve": (SCENE, "grain-dissolve"), "logo-shrink-wordmark-lockup": (SCENE, "logo-shrink-wordmark-lockup"), "neon-triple-marquee": (SCENE, "neon-triple-marquee"),
    "outro-group-photo-launch": (SCENE, "ui-strip-away-outro"), "ui-strip-away-outro": (SCENE, "ui-strip-away-outro"), "ui-to-brand-morph": (SCENE, "logo-shrink-wordmark-lockup"),
    # rhythm
    "beat-cut-moves": (TRANS, "beat-cut-moves"), "beat-step-list-theme-cycle": (TEXT, "type-rhythm-sync"), "panel-grid-moves": (TRANS, "mosaic-reframe"),
    "quad-split-parallel-scenes": (TRANS, "mosaic-reframe"), "rhythm-interrupt-moves": (SCENE, "rhythm-interrupt-moves"), "sakuga-timing-shift": (TEXT, "impact-feedback"),
    "speed-ramp-freeze": (SCENE, "speed-ramp-freeze"), "trailer-grammar-moves": (SCENE, "rhythm-interrupt-moves"),
    # transition
    "bottom-push-stack-wipe": (TRANS, "bottom-push-stack-wipe"), "card-flip-reveal": (TRANS, "card-flip-reveal"), "card-flock-tumble": (TRANS, "card-flock-tumble"),
    "circle-match-iris": (TRANS, "circle-match-iris"), "gradient-transition": (TRANS, "gradient-transition"), "line-carry-transition": (TRANS, "line-carry-transition"),
    "mosaic-reframe": (TRANS, "mosaic-reframe"), "page-turn-transitions": (TRANS, "page-turn-transitions"), "print-texture-transitions": (TRANS, "print-texture-transitions"),
    "shot-transitions": (TRANS, "shot-transitions"), "tear-streak-transitions": (TRANS, "tear-streak-transitions"), "transition-hidden-cut": (TRANS, "transition-hidden-cut"),
    "transition-travel": (TRANS, "transition-travel"), "white-flash-logo-simplify-cut": (TRANS, "white-flash-logo-simplify-cut"), "wipe-transitions": (TRANS, "wipe-transitions"),
    # typography
    "blur-slide": (TEXT, "blur-slide"), "brace-expand": (TEXT, "brace-expand"), "countdown-arc-scatter": (TEXT, "countdown-arc-scatter"),
    "document-typewriter-reveal": (TEXT, "typewriter-moves"), "flying-words": (TEXT, "flying-words"), "glitch-cycle": (TEXT, "glitch-cycle"),
    "gradient-word-sweep": (TEXT, "gradient-word-sweep"), "lead-word-zoom-assemble": (TEXT, "lead-word-zoom-assemble"), "marker-underline-title": (TEXT, "marker-underline-title"),
    "outline-word-fill": (TEXT, "outline-word-fill"), "paper-title-card": (TEXT, "paper-title-card"), "pill-chip-slot-cycle-handled": (TEXT, "pill-slot-cycle"),
    "pill-slot-cycle": (TEXT, "pill-slot-cycle"), "text-column-converge": (TEXT, "flying-words"), "title-demote-to-label": (TEXT, "lead-word-zoom-assemble"),
    "type-assembly-moves": (TEXT, "type-assembly-moves"), "type-entrance-moves": (TEXT, "blur-slide"), "type-rhythm-sync": (TEXT, "type-rhythm-sync"),
    "typewriter-moves": (TEXT, "typewriter-moves"), "vertical-word-roll-blur-cycle": (TEXT, "vertical-word-roll-blur-cycle"), "word-relay-filmstrip": (TEXT, "word-relay-geometry"),
    "word-relay-geometry": (TEXT, "word-relay-geometry"),
    # ui-entrance
    "avatar-bracket-carousel": (TEXT, "scan-bracket-sweep"), "bezier-source-converge-merge": (TEXT, "flying-words"), "card-stack": (TEXT, "deck-deal-flyin"),
    "carousel-3d": (TEXT, "card-flip-reveal"), "cloner-depth-echo": (TEXT, "cloner-depth-echo"), "deck-deal-flyin": (TEXT, "deck-deal-flyin"),
    "doc-park-left-pill-deal": (TEXT, "deck-deal-flyin"), "draw-svg-trace": (TEXT, "draw-svg-trace"), "element-body-moves": (TEXT, "element-body-moves"),
    "integration-hub-map": (TEXT, "radial-wave"), "list-reveal": (TEXT, "blur-slide"), "list-stack-press": (TEXT, "deck-deal-flyin"),
    "neon-frame-forerun": (TEXT, "neon-frame-orbit-drop"), "neon-frame-orbit-drop": (TEXT, "neon-frame-orbit-drop"), "page-waterfall-wall": (TEXT, "vertical-word-roll-blur-cycle"),
    "product-card-progressive-assemble": (TEXT, "type-assembly-moves"), "radial-wave": (TEXT, "radial-wave"), "research-card-stack-scroll": (TEXT, "deck-deal-flyin"),
    "row-embed": (TEXT, "blur-slide"), "value-stagger-gradient": (TEXT, "gradient-word-sweep"), "wall-reveal-moves": (TRANS, "mosaic-reframe"),
}

POOLS = {
    "title": ["lead-word-zoom-assemble", "letterspace-materialize", "slam-entrance-moves", "text-as-mask", "marker-underline-title", "paper-title-card", "type-assembly-moves"],
    "keyword": ["slam-entrance-moves", "blur-slide", "flying-words", "outline-word-fill", "gradient-word-sweep", "vertical-word-roll-blur-cycle", "riso-print-hits",
                "word-relay-geometry", "brace-expand", "spotlight-sweep-moves", "type-rhythm-sync", "lead-word-zoom-assemble"],
    "tag": ["pill-slot-cycle", "deck-deal-flyin", "riso-print-hits", "scan-bracket-sweep", "card-flip-reveal", "glow-flyline-moves"],
    "quote": ["typewriter-moves", "blur-slide", "word-relay-geometry"],
    "sticker": ["radial-wave", "element-body-moves", "deck-deal-flyin", "neon-frame-orbit-drop", "cloner-depth-echo", "impact-feedback", "glow-flyline-moves", "card-flip-reveal"],
    "icon": ["radial-wave", "element-body-moves", "draw-svg-trace", "impact-feedback"],
    "number": ["countdown-arc-scatter"],
    "question": ["glitch-cycle", "type-rhythm-sync", "word-relay-geometry"],
}
CARD_TYPES = {"value_card", "big_number", "price_tag", "stat_row"}
TRANSITIONS = ["circle-match-iris", "wipe-transitions", "white-flash-logo-simplify-cut", "card-flip-reveal", "page-turn-transitions", "mosaic-reframe",
               "gradient-transition", "bottom-push-stack-wipe", "tear-streak-transitions", "line-carry-transition", "shot-transitions", "transition-travel",
               "transition-hidden-cut", "print-texture-transitions", "card-flock-tumble", "beat-cut-moves"]
PUNCHY = ["transition-travel", "shot-transitions", "circle-match-iris", "white-flash-logo-simplify-cut", "beat-cut-moves"]
OPENINGS = ["orbit-ring-title-open", "spotlight-hero-card", "brand-ink-open", "crane-rise-reveal", "fracture"]
OUTROS = ["grain-dissolve", "ui-strip-away-outro", "logo-shrink-wordmark-lockup"]       # neon-triple-marquee is realised but not chosen: its text band collides with labels
CAMERA = ["crash-zoom-punch", "depth-layer-moves", "steep-tilt-glide", "tension-camera-moves"]
RHYTHM = ["speed-ramp-freeze", "rhythm-interrupt-moves"]


def _h(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def _pick(pool: list[str], avoid: list[str], *seed) -> str:
    free = [x for x in pool if x not in avoid] or pool
    return free[_h(*seed) % len(free)]


def _text_of(e: dict) -> str:
    return " ".join(str(e.get(k, "")) for k in ("text", "label", "value", "title") if e.get(k))


def _pool(e: dict) -> list[str] | None:
    t, txt = e.get("type"), _text_of(e)
    if t in CARD_TYPES or (t in ("keyword", "tag", "title") and re.search(r"\d", txt)):
        return POOLS["number"]
    if t in ("keyword", "tag", "title") and txt.strip().endswith("?"):
        return POOLS["question"]
    return POOLS.get(t)


def apply(data: dict, level: str = "auto", seed: str = "vt") -> dict:
    """Give a composition its motion: `fx` per element, `tx` per scene, `moves` per scene. level: auto | subtle | cuts | off. `cuts` keeps the element motion and makes every scene change a plain cut (the reel look)."""
    # Explicit choices also work when automatic motion is disabled.
    for sc in data.get("scenes", []):
        if sc.get("transition_effect", "auto") != "auto":
            sc["tx"] = None if sc["transition_effect"] == "none" else sc["transition_effect"]
        if sc.get("camera_move", "auto") != "auto":
            sc["moves"] = [] if sc["camera_move"] == "none" else [sc["camera_move"]]
        for e in sc.get("elements", []):
            if e.get("entrance", "auto") != "auto":
                e["fx"] = None if e["entrance"] == "none" else e["entrance"]
    if level == "off":
        return data
    scenes = data.get("scenes", [])
    last_fx: list[str] = []
    last_tx: list[str] = []
    n = len(scenes)
    for i, sc in enumerate(scenes):
        for j, e in enumerate(sc.get("elements", [])):
            pool = _pool(e)
            if pool and level in ("auto", "cuts") and e.get("entrance", "auto") == "auto" and not e.get("keyframes"):
                e["fx"] = _pick(pool, last_fx[-2:], seed, sc["id"], j)
                last_fx.append(e["fx"])
        if sc.get("cont") or level == "cuts":                  # a page of the same scene, or a look made of plain cuts: no transition, no scene move
            continue
        if i > 0:
            if level == "subtle" and i % 2:
                continue
            if _h(seed, "calm", i) % 4 == 0 and i > 3:            # one scene in four keeps the plain cut or fade: rhythm needs rests
                continue
            tx = _pick(PUNCHY if i < 4 else TRANSITIONS, last_tx[-2:], seed, "tx", i)
            if sc.get("transition_effect", "auto") == "auto": sc["tx"] = tx
            last_tx.append(tx)
        moves = []
        if level == "auto":
            if i == 0:
                moves.append(_pick(OPENINGS, [], seed, "open"))
            elif i == n - 1:
                moves.append(_pick(OUTROS, [], seed, "out"))
            elif i % 5 == 3 and not sc.get("stick"):
                moves.append(_pick(CAMERA, [], seed, "cam", i))
            elif i % 8 == 6:
                moves.append(_pick(RHYTHM, [], seed, "rh", i))
        if moves and sc.get("camera_move", "auto") == "auto":
            sc["moves"] = moves
    data["motion"] = level
    return data
