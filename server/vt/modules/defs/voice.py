"""The voice modules: list voices, speak one sentence or a whole script, describe or design a voice, clone one from a short recording.

They sit on `vt/tts.py` (one call for every engine: Edge, Kokoro, MMS, a cloned voice, a voice in ComfyUI, another computer's engine), so a director gets all of them through the same
four verbs. An engine that is not reachable fails with a sentence; nothing here silently switches voice, because a changed voice is something the person must be told.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


def _duration(wav: Path) -> float:
    import soundfile as sf

    info = sf.info(str(wav))
    return round(info.frames / info.samplerate, 3)


class ListIn(BaseModel):
    language: str = Field(default="", description="Only voices for this language code (bn, en, hi...); empty lists all.")


class ListOut(BaseModel):
    voices: list[dict[str, Any]] = Field(description="Per voice: id as 'engine:voice', label, language, engine and whether it can follow delivery notes.")
    engines: list[str] = Field(description="The engines that answered.")


@module(
    id="voice.list", version=1, summary="Every voice the app can speak with, from every engine that is ready, as 'engine:voice'.",
    when_to_use="Before choosing a voice for a script.", when_not_to_use="When the voice is already chosen.",
    inputs=ListIn, outputs=ListOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 2.0), effects="none", determinism="external", grounding=(),
    fallback=None, fallback_reason="An engine that does not answer is left out of the list; the others still show.",
    examples=(Example(inputs={"language": "en"}, outputs={"voices": [{"id": "kokoro:af_heart", "label": "Heart", "language": "en", "engine": "kokoro", "direction": False}], "engines": ["kokoro"]}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Listing the voices", native_outputs=True,
    log_line=lambda i, o: f"Found {len(o.voices)} voices in {len(o.engines)} engine{'s' if len(o.engines) != 1 else ''}.",
)
def list_voices(ws: Workspace, inputs: ListIn) -> ListOut:
    from ... import tts

    voices, engines = [], []
    for e in tts.list_engines():
        if not e.get("available", True):
            continue
        engines.append(e["id"])
        for v in e.get("voices", []):
            lang = str(v.get("lang", "") or v.get("language", ""))
            if inputs.language and lang and not lang.lower().startswith(inputs.language.lower()):
                continue
            voices.append({"id": f"{e['id']}:{v['id']}", "label": v.get("label", v["id"]), "language": lang, "engine": e["id"], "direction": bool(e.get("direction"))})
    return ListOut(voices=voices, engines=engines)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="One sentence or short passage to speak.")
    voice: str = Field(default="auto:auto", description="Best ready voice by default; or 'engine:voice', as listed by voice.list.")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speed: 1.0 is natural.")
    instruction: str = Field(default="", max_length=300, description="Delivery notes for engines that follow them ('whisper', 'warm, slow').")
    language: str = Field(default="en", description="Language code of the text.")


class SpeakOut(BaseModel):
    audio: str = Field(description="Path of the spoken sentence (wav) inside the project.")
    seconds: float = Field(description="How long it lasts.")
    engine: str = Field(description="The engine that spoke it.")


@module(
    id="voice.speak", version=1, summary="Speak one sentence in a chosen voice; the sound is a file in the project.",
    when_to_use="A sentence needs a voice: a hook, a retake of one line, a preview of a voice.", when_not_to_use="For a whole script (voice.speak_script keeps the timings).",
    inputs=SpeakIn, outputs=SpeakOut, requires=(), produces=("audio.sentence",), cost=Cost("slow", ("gpu",), 8.0), effects="writes_artifact", determinism="seeded", grounding=("text",),
    fallback=None, fallback_reason="A voice that cannot speak says why; the voice is never changed without telling the person.",
    examples=(Example(inputs={"text": "Hello there."}, outputs={"audio": "speech/sentence.wav", "seconds": 1.1, "engine": "edge"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Speaking a sentence", native_outputs=True,
    log_line=lambda i, o: f"Spoke one sentence ({o.seconds:.1f} s) with {o.engine}.",
)
def speak(ws: Workspace, inputs: SpeakIn) -> SpeakOut:
    from ... import tts

    engine, _, voice = inputs.voice.partition(":")
    if engine == 'auto':
        engine, voice = tts.recommended_voice(inputs.language)
        if engine == 'comfyvoice' and voice == 'design:auto':
            from ...comfy.voicing import cast
            voice = cast(inputs.text)
    out = ws.root / "speech" / "sentence.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    tts.synth_sentence(engine, voice, inputs.text, inputs.rate, out, inputs.instruction, inputs.language)
    return SpeakOut(audio=str(out.relative_to(ws.root)), seconds=_duration(out), engine=engine)


class ScriptIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000, description="The whole script.")
    voice: str = Field(default="auto:auto", description="Best ready voice by default; 'comfyvoice:design:auto' lets the director cast a voice from the content.")
    rate: float = Field(default=1.0, ge=0.5, le=2.0, description="Speed: 1.0 is natural.")
    language: str = Field(default="", description="Language code; empty detects it.")


class ScriptOut(BaseModel):
    audio: str = Field(description="Path of the spoken script (wav) inside the project.")
    seconds: float = Field(description="How long it lasts.")
    sentences: int = Field(description="How many sentences were spoken.")
    words: list[dict[str, Any]] = Field(description="Every spoken word with its start and end time in seconds.")
    engine: str = Field(description="The engine that spoke it.")
    voice: str = Field(description="The voice that was used (a cast voice shows what was chosen).")


@module(
    id="voice.speak_script", version=1, summary="Speak a whole script sentence by sentence; returns the sound and the real time of every word.",
    when_to_use="The audio-first voice step: the words and their times are exact because they come from the voice, not from guessing.", when_not_to_use="For a recording a person made.",
    inputs=ScriptIn, outputs=ScriptOut, requires=(), produces=(), cost=Cost("slow", ("gpu",), 60.0), effects="writes_artifact", determinism="seeded", grounding=("text",),
    fallback=None, fallback_reason="A voice that cannot speak says why; the script is never read in another voice without telling the person.",
    examples=(Example(inputs={"text": "One. Two."}, outputs={"audio": "speech/script.wav", "seconds": 2.0, "sentences": 2, "words": [], "engine": "edge", "voice": "en-US-AriaNeural"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Reading the script aloud", native_outputs=True,
    log_line=lambda i, o: f"Read {o.sentences} sentences aloud ({o.seconds:.0f} s) with {o.engine}.",
)
def speak_script(ws: Workspace, inputs: ScriptIn) -> ScriptOut:
    from ... import tts

    engine, _, voice = inputs.voice.partition(":")
    out = ws.root / "speech" / "script.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = tts.synthesize(inputs.text, out, engine=engine, voice=voice, rate=inputs.rate, language=inputs.language)
    words = [w for s in r.get("sentences", []) for w in s.get("words", [])]
    return ScriptOut(audio=str(out.relative_to(ws.root)), seconds=float(r.get("duration") or _duration(out)), sentences=len(r.get("sentences", [])), words=words, engine=r.get("engine", engine),
                     voice=str(r.get("voice", voice)))


class DescribeIn(BaseModel):
    description: str = Field(min_length=1, max_length=300, description="A voice in words: 'a warm older man, slow' or 'a bright young woman'.")


class DescribeOut(BaseModel):
    instruction: str = Field(description="What the voice engine is asked for (for example: male, elderly, low pitch).")
    voice: str = Field(description="The voice id to use with voice.speak: 'comfyvoice:design:<description>'.")


@module(
    id="voice.describe", version=1, summary="Say what a voice description maps to, without speaking anything.",
    when_to_use="To show the person what a description will ask the engine for.", when_not_to_use="To hear it; voice.design speaks a sample.",
    inputs=DescribeIn, outputs=DescribeOut, requires=(), produces=(), cost=Cost("instant", ("cpu",), 0.01), effects="none", determinism="pure", grounding=(),
    fallback=None, fallback_reason="It is a word-to-attribute mapping with no model.",
    examples=(Example(inputs={"description": "a deep older man, slow"}, outputs={"instruction": "male, elderly, low pitch", "voice": "comfyvoice:design:a deep older man, slow"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Describing a voice", native_outputs=True,
    log_line=lambda i, o: f"“{i.description[:40]}” means: {o.instruction}.",
)
def describe(ws: Workspace, inputs: DescribeIn) -> DescribeOut:
    from ...comfy import voicing

    return DescribeOut(instruction=voicing.omnivoice_instruct(inputs.description), voice=f"comfyvoice:design:{inputs.description.strip()}")


class DesignIn(BaseModel):
    description: str = Field(min_length=1, max_length=300, description="The voice in words.")
    sample: str = Field(default="This is how I sound.", max_length=300, description="What the sample says.")


class DesignOut(BaseModel):
    voice: str = Field(description="The voice id to use with voice.speak.")
    audio: str = Field(description="Path of the sample (wav).")
    seconds: float = Field(description="Length of the sample.")
    instruction: str = Field(description="What the engine was asked for.")


@module(
    id="voice.design", version=1, summary="Make a voice from a description and speak a short sample so the person can hear it.",
    when_to_use="The person describes a voice instead of picking one.", when_not_to_use="When a listed voice already fits.",
    inputs=DesignIn, outputs=DesignOut, requires=(), produces=("audio.sentence",), cost=Cost("slow", ("gpu",), 10.0), effects="writes_artifact", determinism="seeded", grounding=(),
    fallback=None, fallback_reason="Voice design needs a voice model in ComfyUI (Breeze or OmniVoice); without one it says so.",
    examples=(Example(inputs={"description": "a warm older man"}, outputs={"voice": "comfyvoice:design:a warm older man", "audio": "speech/sentence.wav", "seconds": 2.0, "instruction": "male, elderly"}),),
    toolboxes=("autonomous", "studio", "full"), plain_name="Designing a voice", native_outputs=True,
    log_line=lambda i, o: f"Designed a voice from “{i.description[:40]}” and made a {o.seconds:.1f} s sample.",
)
def design(ws: Workspace, inputs: DesignIn) -> DesignOut:
    from ... import tts
    from ...comfy import voicing

    d = describe(ws, DescribeIn(description=inputs.description))
    out = ws.root / "speech" / "sentence.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    tts.synth_sentence("comfyvoice", f"design:{inputs.description.strip()}", inputs.sample, 1.0, out, d.instruction)
    return DesignOut(voice=d.voice, audio=str(out.relative_to(ws.root)), seconds=_duration(out), instruction=d.instruction)


class CloneIn(BaseModel):
    audio: str = Field(description="Path of a short recording of the voice (10 to 30 seconds of clear speech), inside the project or an absolute path.")
    name: str = Field(min_length=1, max_length=60, description="A name for the voice.")
    consent: bool = Field(description="True only if this is the person's own voice or the speaker allowed it. A voice is never cloned without it.")


class CloneOut(BaseModel):
    voice: str = Field(description="The voice id to use with voice.speak: 'clone:<id>'.")
    name: str = Field(description="The name it was given.")
    seconds: float = Field(description="How much of the recording was kept as the reference.")


@module(
    id="voice.clone", version=1, summary="Make a voice profile from a short recording, with the speaker's consent recorded.",
    when_to_use="The person supplied their own recording and agreed.", when_not_to_use="Without consent, or with someone else's recording.",
    inputs=CloneIn, outputs=CloneOut, requires=(), produces=(), cost=Cost("fast", ("cpu",), 5.0), effects="writes_artifact", determinism="pure", grounding=(),
    fallback=None, fallback_reason="Cloning is refused without consent; there is no other way to get the voice.",
    examples=(Example(inputs={"audio": "my_voice.wav", "name": "Me", "consent": True}, outputs={"voice": "clone:me", "name": "Me", "seconds": 18.0}),),
    toolboxes=("studio", "full"), plain_name="Cloning a voice", native_outputs=True,
    log_line=lambda i, o: f"Saved the voice “{o.name}” from a {o.seconds:.0f} s recording.",
)
def clone(ws: Workspace, inputs: CloneIn) -> CloneOut:
    from ... import voices as V

    src = Path(inputs.audio)
    if not src.is_absolute():
        src = ws.root / src
    if not src.is_file():
        raise V.VoiceError(f"There is no recording at {inputs.audio}.")
    v = V.add_voice(src, inputs.name, inputs.consent)
    return CloneOut(voice=f"clone:{v['id']}", name=v["name"], seconds=float(v.get("seconds", 0.0)))
