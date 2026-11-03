"""Audio-first analysis modules introduced by the director plan."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..registry import Cost, Example, module
from ..workspace import Workspace


class SaliencyIn(BaseModel):
    hop_seconds: float = Field(default=0.05, ge=0.01, le=0.25, description="Output curve step in seconds.")


class SaliencyOut(BaseModel):
    points: list[dict[str, float]] = Field(description="Time-only normalized auditory saliency curve.")


@module(id="audio.saliency", version=1, summary="Measure a time-only auditory saliency curve from loudness and spectral change.",
        when_to_use="Finding picture-change candidates independent of recognized words.", when_not_to_use="No master audio exists.",
        inputs=SaliencyIn, outputs=SaliencyOut, requires=("audio.master",), produces=("audio.saliency",), cost=Cost("fast", ("cpu",), 4.0),
        effects="writes_artifact", determinism="pure", grounding=(), fallback=None, fallback_reason="A flat or silent signal safely returns zero saliency.",
        examples=(Example(inputs={"hop_seconds": 0.05}, outputs={"points": []}),), toolboxes=("autonomous", "studio", "full"),
        plain_name="Measuring auditory saliency", log_line=lambda i, o: f"Measured {len(o.points)} auditory saliency points.")
def auditory_saliency(ws: Workspace, inputs: SaliencyIn) -> SaliencyOut:
    import numpy as np
    import soundfile as sf
    audio, sr = sf.read(str(ws.path_for("audio.master")), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    hop = max(1, round(sr * inputs.hop_seconds)); frame = max(hop * 2, round(sr * 0.1))
    if len(mono) < frame:
        return SaliencyOut(points=[])
    window = np.hanning(frame)
    spectra = np.asarray([np.abs(np.fft.rfft(mono[start:start + frame] * window))
                          for start in range(0, len(mono) - frame + 1, hop)])
    rms = np.asarray([np.sqrt(np.mean(mono[start:start + frame] ** 2) + 1e-12)
                      for start in range(0, len(mono) - frame + 1, hop)])
    flux = np.r_[0.0, np.maximum(0.0, np.diff(spectra, axis=0)).sum(axis=1)]
    def norm(values):
        lo, hi = np.percentile(values, [10, 95])
        return np.clip((values - lo) / max(1e-9, hi - lo), 0, 1)
    score = 0.45 * norm(rms) + 0.55 * norm(flux)
    return SaliencyOut(points=[{"time": round((index * hop + frame / 2) / sr, 3), "strength": round(float(value), 4)}
                               for index, value in enumerate(score)])


class AlignIn(BaseModel):
    wav: str = Field(description="Spoken sentence wave file.")
    text: str = Field(min_length=1, description="Exact sentence spoken in the wave file.")


class AlignOut(BaseModel):
    words: list[dict[str, float | str]] = Field(description="Measured and silence-snapped word onset and end times.")


@module(id="audio.align_words", version=1, summary="Measure sentence word timing from its waveform and snap boundaries to real quiet gaps.",
        when_to_use="A synthesized sentence needs impact-cut word onsets.", when_not_to_use="Word timings already came from speech recognition.",
        inputs=AlignIn, outputs=AlignOut, requires=(), produces=(), cost=Cost("slow", ("cpu",), 8.0), effects="none", determinism="pure",
        grounding=("text",), fallback=None, fallback_reason="The existing waveform timing estimator supplies a deterministic alignment.",
        examples=(Example(inputs={"wav": "sentence.wav", "text": "Hello world"}, outputs={"words": []}),),
        toolboxes=("autonomous", "studio", "full"), plain_name="Aligning spoken words", log_line=lambda i, o: f"Aligned {len(o.words)} spoken word(s).")
def align_words(ws: Workspace, inputs: AlignIn) -> AlignOut:
    import soundfile as sf
    from ...tts import word_times
    audio, sr = sf.read(str(Path(inputs.wav)), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    tokens = inputs.text.split()
    times = word_times(tokens, mono, sr)
    return AlignOut(words=[{"text": token, "start": round(start, 3), "end": round(end, 3)}
                           for token, (start, end) in zip(tokens, times)])
