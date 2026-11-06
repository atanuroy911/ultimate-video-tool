"""A picture video with no face on camera (a screen recording, a tutorial) is edited as a protected recording by default: its own picture and pauses, plus captions.
Graphics on top are an explicit choice ("screen"). Before this, "auto" ran the whole explainer treatment on it: a random transition on 45 of 49 scenes, 32 keyword
badges, 18 stickers and a full-screen cream card (judged on recording 2, 2026-11-03)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "server"


def sub(path, old, new):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    assert old in s, (path, old[:70])
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


sub("vt/source_inspect.py", "def inspect_source(path: Path) -> dict:", '''def default_recording_edit(info: dict, chosen: str = "auto") -> str:
    """The recording mode a new project starts in. The person's own choice ('subtitles' or 'screen') always stands. 'auto' becomes 'subtitles' for a video that
    shows a picture without a person talking to the camera (a screen recording or tutorial: the viewer needs that picture untouched, with captions), and stays
    'auto' for a talking head or audio, which the normal editing suits."""
    if chosen in ("subtitles", "screen"):
        return chosen
    return "subtitles" if info.get("mode") == "video" and info.get("has_picture") else "auto"


def inspect_source(path: Path) -> dict:''')

sub("vt/server/app.py", '''        write_json(p.dir / "source.json", _inspect(tmp))''', '''        info = _inspect(tmp)
        write_json(p.dir / "source.json", info)
        from ..source_inspect import default_recording_edit

        mode = default_recording_edit(info, p.meta().options.recording_edit)
        if mode != p.meta().options.recording_edit:               # a screen recording starts protected: its picture and pauses kept, captions added
            m = p.meta()
            m.options.recording_edit = mode
            p.save_meta(m)''')
print("ok")
