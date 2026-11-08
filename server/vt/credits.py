"""The one credits text for a video: stock and catalogue media, the music track when its licence asks for a credit (Bensound's free
licence does), and where the voice and words came from for a video made from a link. The export writes it next to the MP4, the
publishing text appends it to the description, the `publish.credits` module returns it, and the Studio shows it with a Copy button."""
from __future__ import annotations

from typing import Optional


def text(project, music_id: Optional[str] = None) -> str:
    """Plain-text credits ('' when everything is the person's own). `music_id` defaults to the project's chosen track."""
    from .director.catalog import music_credit
    from .director.stock import credits_text

    meta = project.meta()
    if music_id is None:
        music_id = getattr(meta.options, "music", None)
    if music_id in ("auto", ""):
        music_id = None
    credits = credits_text(project)
    mc = music_credit(music_id)
    if mc:
        credits = (credits or "Media credits\n") + f"- {mc}\n"
    origin = meta.origin
    if origin:
        lines = [f"Voice and text from: {origin.get('title', '')} by {origin.get('uploader') or 'unknown'}", origin.get("url", "")]
        if origin.get("license"):
            lines.append(f"Licence: {origin['license']}")
        credits = (credits or "") + "\n".join(x for x in lines if x) + "\n"
    return credits


def with_description(description: str, credits: str) -> str:
    """The description a person posts: their words, then the credits the licences ask for (once)."""
    credits = (credits or "").strip()
    description = (description or "").rstrip()
    if not credits or credits in description:
        return description
    return f"{description}\n\n{credits}" if description else credits
