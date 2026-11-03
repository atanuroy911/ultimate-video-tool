"""One look for the whole video: the same drawing style, and the same figure, in every picture (the first thing the example reels share)."""
from __future__ import annotations

import re

STYLES: dict[str, dict] = {
    "cartoon": {"label": "Clean cartoon", "text": "flat 2D cartoon illustration, bold black outlines, simple clean shapes, soft muted blue-grey background, one clear subject, vertical composition"},
    "line-art": {"label": "Pencil line art", "text": "minimal pencil line drawing on light grey paper, thin black lines, soft vignette, simple stick-like people, one clear idea, vertical composition"},
    "comic": {"label": "Inked comic", "text": "hand-inked comic panel, expressive round-headed figure, muted colour palette with one warm accent, dramatic lighting, vertical composition"},
    "photo": {"label": "Cinematic photo", "text": "cinematic photograph, natural light, shallow depth of field, realistic, one clear subject, vertical composition"},
}
# the recurring figure when the AI gave none: the same one in every picture is what makes separate pictures read as one story
FIGURE = {"cartoon": "a friendly cartoon man with a round head, short black hair and a beige coat",
          "line-art": "a simple stick-like person with a round head",
          "comic": "a round-headed figure in a red scarf",
          "photo": ""}
NO_TEXT = "no text, no letters, no words, no captions, no watermark"


def drawing_style(style: str, theme: str = "") -> str:
    """The style the pictures are drawn in: a film style theme ('style-<slug>') draws them too, else the reel style."""
    return "film:" + theme[6:] if (theme or "").startswith("style-") else style


def film_style_text(slug: str) -> str:
    """A film style (design/styles, vt/styles.py) as a picture look: its one-line essence and its colour logic, condensed for the picture model."""
    import re

    from .. import styles as S

    b = S.get(slug)
    if not b:
        return STYLES["cartoon"]["text"]
    clip = lambda t, n: " ".join(re.sub(r"\(.*?\)|\*", "", t).split()[:n])           # noqa: E731
    parts = [clip(b["summary"], 32)] + [clip(x, 22) for x in (b.get("colour") or [])[:1]]        # materials describe the film engine, not the picture
    # pictures never carry words (the captions do): clauses about notes, labels or type would make the model paint lettering
    # nor clauses about the film as an object (a journal page, a sheet that paints itself): the model paints a notebook instead of the scene
    wordy = re.compile(r"\b(note|notes|label|labels|annotation|annotations|text|type|lettering|subtitle|caption|written|title|journal|page|pages|"
                       r"notebook|book|sheet|paints itself|draws itself|animated|animation|frame by frame|film)\b", re.I)
    keep = [c.strip() for p in parts for c in re.split(r"[,:;]", p) if c.strip() and not wordy.search(c)]
    return f"{b['name']} style, " + ", ".join(k.rstrip(".") for k in keep) + ", one clear subject, vertical composition"   # the style's name is the strongest cue


def cast_for(draw: str, cast: dict) -> str:
    """The looks of the people a shot names ("Mira: an eleven-year-old girl ..."), in the order they appear; the others are left out."""
    found = sorted(((m.start(), n) for n in cast for m in [re.search(rf"\b{re.escape(n)}\b", draw, re.I)] if m), key=lambda x: x[0])
    return "; ".join(f"{n}: {cast[n].strip().rstrip('.')}" for _, n in found)


def prompt_for(draw: str, style: str, character: str = "", place: str = "") -> str:
    """The picture prompt: what to show, where (the place's description: each picture is painted alone, so it must say where and how big),
    the recurring figure (if any), then the look. Pictures never carry words: the captions do.
    `style` is one of STYLES or 'film:<slug>' for one of the 66 film styles."""
    s = film_style_text(style[5:]) if style.startswith("film:") else STYLES.get(style, STYLES["cartoon"])["text"]
    if CLOSE.match(draw) and place.strip():                         # a full room description pulls every model back to a wide shot: keep only a soft hint
        where = f" Tight framing, the subject fills the whole frame; background softly out of focus: {_short_place(place)}."
    else:
        where = f" Setting: {place.strip().rstrip('.')}." if place.strip() else ""
    who = f" The same recurring figure: {character}." if character else ""
    return f"{draw.strip().rstrip('.')}.{where}{who} {s}. {NO_TEXT}."


CLOSE = re.compile(r"^\W*(extreme\s+)?close[- ]?up\b|^\W*macro\b", re.I)


def _short_place(place: str) -> str:
    """The background of a close-up: what is visible right behind the subject, not the place's name.
    'inside the round glass lantern room at the top of the lighthouse: windows all round, an iron floor, ...' -> 'windows all round, an iron floor'.
    The name drew the outside of the lighthouse behind a close-up set inside it (The Last Lamp, 2026-11-01)."""
    head, _, details = place.partition(":")
    items = [x.strip() for x in re.split(r"[,;]", details) if x.strip()]
    if items:
        return ", ".join(items[:2]).rstrip(".")
    return re.sub(r"^\s*(inside|in|on|at|aboard)\s+", "", head.strip(), flags=re.I).rstrip(".") or place[:80]
