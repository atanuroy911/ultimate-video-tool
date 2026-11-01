"""Words the speech model invents (seen on the owner's Bangla sample, 2026-10-23: "উড়ে চলে গেল ট্রেনের" at the end of the story)."""
from vt.stages.asr import looped


def test_a_looping_segment_is_recognised():
    assert looped(["ট্রেনের", "প্রেসিডেন্ট", "প্রেসিডেন্ট", "প্রেসিডেন্ট"])
    assert not looped(["never,", "never", "give", "up"])
    assert not looped(["এই", "গল্প", "থেকে", "আমরা"])


def test_low_confidence_words_from_invented_segments_are_dropped(monkeypatch):
    """The transcription loop with a stand-in model: one real segment that ends in an invented word, one looping segment."""
    import numpy as np

    from vt.stages import asr

    class W:
        def __init__(self, word, start, end, p):
            self.word, self.start, self.end, self.probability = word, start, end, p

    class Seg:
        def __init__(self, words, nsp=0.0, lp=-0.2):
            self.words, self.no_speech_prob, self.avg_logprob, self.end, self.text = words, nsp, lp, words[-1].end, " ".join(w.word for w in words)

    class Model:
        def __init__(self, *a, **k):
            self.n = 0

        def transcribe(self, piece, **k):
            self.n += 1
            if self.n == 1:
                return [Seg([W(" উড়ে", 0.0, 0.4, 1.0), W(" চলে", 0.4, 0.8, 1.0), W(" গেল", 0.8, 1.1, 1.0), W(" ট্রেনের", 1.1, 1.6, 0.59)])], None
            return [Seg([W(" ট্রেনের", 0.0, 0.5, 0.6), W(" প্রেসিডেন্ট", 0.5, 1.0, 0.6), W(" প্রেসিডেন্ট", 1.0, 1.5, 0.6), W(" প্রেসিডেন্ট", 1.5, 2.0, 0.6)])], None

    monkeypatch.setattr("faster_whisper.WhisperModel", Model)
    monkeypatch.setattr("faster_whisper.vad.get_speech_timestamps", lambda piece, opts: [{"start": 0, "end": len(piece)}])
    monkeypatch.setattr(asr, "ensure_model", lambda *a, **k: "x")
    monkeypatch.setattr(asr, "cuda_available", lambda: False)
    import soundfile as sf
    import pathlib
    import tempfile

    wav = pathlib.Path(tempfile.mkdtemp()) / "a.wav"
    sf.write(wav, np.zeros(16000 * 6, dtype="float32"), 16000)
    res = asr.transcribe(wav, model="bn-medium", language="bn", chunks=[(0.0, 3.0), (3.0, 6.0)])
    assert [w["text"] for w in res["words"]] == ["উড়ে", "চলে", "গেল"]
