"""English by default, and a script is always spoken in the language of its letters (owner, 2026-11-01: "the script is in english you
generated bangla audio"; Bangla is paused). One guard in Project.create_from_script covers the API, the CLI and MCP."""
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def sub(path, old, new, count=1):
    p = R / path
    s = p.read_text(encoding="utf-8")
    assert s.count(old) >= count, (path, old[:70])
    p.write_text(s.replace(old, new, count), encoding="utf-8")


sub("vt/project.py", '''    def create_from_script(cls, title: str, script: str, *, voice_engine: str = "edge", voice: str = "bn-BD-NabanitaNeural", rate: float = 1.0,
                           language: str = "bn", aspect: str = "9:16", theme: str = "paper", pace: str = "normal",
                           options: Optional[dict] = None) -> "Project":
        """A project whose voice is synthesised from `script` by the first pipeline stage ('voice')."""
        import tempfile
''', '''    def create_from_script(cls, title: str, script: str, *, voice_engine: str = "edge", voice: str = "en-US-AndrewNeural", rate: float = 1.0,
                           language: str = "en", aspect: str = "9:16", theme: str = "paper", pace: str = "normal",
                           options: Optional[dict] = None) -> "Project":
        """A project whose voice is synthesised from `script` by the first pipeline stage ('voice').
        The script is spoken in the language of its letters whatever was asked: an English script read by a Bangla voice (or the other way
        round) is never right, so the language and the voice are corrected to match the text."""
        import tempfile

        from . import tts

        language, voice = tts.match_script(script, language, voice_engine, voice)
''')
tts = R / "vt/tts.py"
t = tts.read_text(encoding="utf-8")
t += '''

def match_script(script: str, language: str, engine: str, voice: str) -> tuple[str, str]:
    """(language, voice) that fit the script's letters: English text gets English and an English voice of the same engine, Bangla text
    Bangla and a Bangla voice. A voice that already fits is kept, so a chosen voice is never replaced without need."""
    from . import langdetect

    want = langdetect.from_text(script, default="en")
    want = want if want in ("en", "bn") else language if language in ("en", "bn") else "en"
    try:
        voices = next(e for e in list_engines() if e["id"] == engine)["voices"]
    except (StopIteration, KeyError):
        return want, voice
    if any(v["id"] == voice and v["lang"].startswith(want) for v in voices):
        return want, voice
    return want, next((v["id"] for v in voices if v["lang"].startswith(want)), voice)
'''
tts.write_text(t, encoding="utf-8")

sub("vt/server/app.py", '''    language: str = "bn"
    engine: str = "edge"
    voice: str = "bn-BD-NabanitaNeural"''', '''    language: str = "auto"
    engine: str = "edge"
    voice: str = "en-US-AndrewNeural"''')
sub("vt/server/app.py", '''title: str = Form(""), language: str = Form("bn"),''', '''title: str = Form(""), language: str = Form("en"),''')
sub("vt/cli.py", '''           voice: str = typer.Option("bn-BD-NabanitaNeural", "--voice"),''', '''           voice: str = typer.Option("en-US-AndrewNeural", "--voice"),''')
sub("vt/cli.py", '''           language: str = typer.Option("bn", "--lang"), aspect: str = typer.Option("9:16", "--aspect"),''',
    '''           language: str = typer.Option("en", "--lang", help="en or bn; the script's letters decide in the end"), aspect: str = typer.Option("9:16", "--aspect"),''')
sub("vt/cli.py", '''        language: str = typer.Option("bn", "--lang", help="bn or en"),''', '''        language: str = typer.Option("en", "--lang", help="en or bn"),''')
sub("studio/src/pages/New.tsx", '''  const [voice, setVoiceRaw] = useState("bn-BD-NabanitaNeural");''', '''  const [voice, setVoiceRaw] = useState("en-US-AndrewNeural");''')
print("ok")
