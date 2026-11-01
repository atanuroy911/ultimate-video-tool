"""One look for the whole video: the same drawing style, and the same figure, in every picture (the first thing the example reels share)."""
from __future__ import annotations

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


def prompt_for(draw: str, style: str, character: str = "") -> str:
    """The picture prompt: what to show, the recurring figure (if any), then the look. Pictures never carry words: the captions do."""
    s = STYLES.get(style, STYLES["cartoon"])["text"]
    who = f" The same recurring figure: {character}." if character else ""
    return f"{draw.strip().rstrip('.')}.{who} {s}. {NO_TEXT}."
