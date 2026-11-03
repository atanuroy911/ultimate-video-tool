"""Built-in module adapters; importing this package does not load ML libraries."""


def load() -> None:
    from . import audio, audio_first_new, core, craft, cut, direction, fill, gen, judge, media, meta, phase2_remaining, plan, project, project_media, pipeline_stages, reel, remaining, render, shorts, styles, text, timeline, voice  # noqa: F401
