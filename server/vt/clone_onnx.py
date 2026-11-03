"""Voice cloning with Chatterbox Turbo (Resemble AI, MIT) run through ONNX Runtime, in this app's own Python environment.

A port of the reference in Concat (`concat-speech/src/chatterbox.rs`, jub0t/concat), function by function and with the same names, so the two can be compared line by line. Four networks:
a speech encoder (a few seconds of someone talking -> what the voice sounds like), a text embedding, a language model that writes speech tokens one at a time with a key-value cache,
and a decoder that turns the tokens into 24 kHz sound. Tags the model was taught (`[laugh]`, `[chuckle]`, `[sigh]`) are read as what they say. Resemble's Python stamps its output with
a watermark; the ONNX path has none, and this adds none.

The one thing the export is particular about: the embedding graph splits whatever ids it is given into two runs. Everything but the last two goes through the text table, the last two through
the speech table with `<|endoftext|>` (50256) swapped for the start-of-speech token (6561). The tokenizer appends two `<|endoftext|>` to every text, so the whole output, terminators
included, is embedded in one call. Nothing else may be appended.

Graphs (names the code uses; checked against the files by `tests/test_clone_onnx.py::test_the_graphs_have_the_names_the_code_feeds`):
  speech_encoder   in  audio_values [1, N] f32 (24 kHz)       out audio_features [1, T, 1024], audio_tokens [1, K] i64, speaker_embeddings [1, 192], speaker_features [1, F, 80]
  embed_tokens     in  input_ids [1, n] i64                    out inputs_embeds [1, n, 1024]
  language_model   in  inputs_embeds, attention_mask [1, total] i64, position_ids [1, n] i64, past_key_values.{0..23}.{key,value} [1, 16, past, 64]
                   out logits [1, n, vocab], present.{0..23}.{key,value}
  conditional_decoder  in speech_tokens [1, M] i64, speaker_embeddings, speaker_features   out waveform
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

SAMPLE_RATE = 24_000
TOKENS_PER_SECOND = 25.0
START_SPEECH_TOKEN = 6561
TEXT_END_TOKEN = 50256
STOP_SPEECH_TOKEN = 6562
SILENCE_TOKEN = 4299
KV_HEADS = 16
HEAD_DIM = 64
LAYERS = 24
REPETITION_PENALTY = 1.2
TEMPERATURE = 0.8
TOP_K = 1000
TOP_P = 0.95
MAX_NEW_TOKENS = 1024
RUNAWAY = 4
MIN_REFERENCE_SECONDS = 5.0
TARGET_LUFS = -27.0
CHUNK_CHARS = 250
GAP_SECONDS = 0.25
MASK64 = (1 << 64) - 1


class CloneError(RuntimeError):
    pass


class Cancelled(CloneError):
    pass


class Rng:
    """xorshift64*, the draw a sample takes; a seed gives the same draws as the Rust one."""

    def __init__(self, seed: int):
        self.s = (seed & MASK64) or 0x9E3779B97F4A7C15

    @classmethod
    def seeded(cls) -> "Rng":
        import os
        return cls((time.time_ns() ^ (os.getpid() << 32)) & MASK64)

    def unit(self) -> float:
        """Uniform in [0, 1)."""
        x = self.s
        x ^= x >> 12
        x ^= (x << 25) & MASK64
        x ^= x >> 27
        self.s = x
        word = (x * 0x2545F4914F6CDD1D) & MASK64
        return float(np.float32(word >> 40) / np.float32(1 << 24))


def _penalised(logits: np.ndarray, written, penalty: float) -> np.ndarray:
    out = np.array(logits, dtype=np.float32, copy=True)
    idx = np.unique(np.asarray([i for i in written if 0 <= i < len(out)], dtype=np.int64))
    if idx.size:
        v = out[idx]
        out[idx] = np.where(v < 0, v * np.float32(penalty), v / np.float32(penalty))
    return out


def next_token(logits, written, penalty: float) -> int:
    """The most likely next token, every token already written made `penalty` times less likely (a score below zero is multiplied, one above divided). Ties go to the first; NaN never wins."""
    logits = np.asarray(logits, dtype=np.float32)
    if logits.size == 0:
        return 0
    s = np.nan_to_num(_penalised(logits, written, penalty), nan=-np.inf)
    return int(np.argmax(s))


def sample_token(logits, written, penalty: float, temperature: float, top_k: int, top_p: float, rng: Rng) -> int:
    """Resemble's draw: the repetition penalty, the logits over `temperature`, the `top_k` likeliest kept, one drawn from the smallest set of those whose probability adds up to `top_p`.
    A temperature of zero is the argmax."""
    logits = np.asarray(logits, dtype=np.float32)
    if temperature <= 0.0 or logits.size == 0:
        return next_token(logits, written, penalty)
    s = _penalised(logits, written, penalty)
    s[~np.isfinite(s)] = -np.inf
    order = np.argsort(-s, kind="stable")[:max(1, top_k)]
    scores = s[order]
    top = scores[0]
    if not np.isfinite(top):
        return int(order[0])
    weights = np.exp((scores - top) / np.float32(temperature)).astype(np.float32)
    total = float(weights.sum(dtype=np.float32))
    cutoff = min(max(top_p, 0.0), 1.0) * total
    cum = np.cumsum(weights, dtype=np.float32)
    kept = int(np.searchsorted(cum, cutoff, side="left")) + 1                       # the first prefix whose sum reaches the cutoff
    kept = min(kept, len(weights))
    covered = float(cum[kept - 1])
    draw = rng.unit() * covered
    below = np.cumsum(weights[:kept], dtype=np.float32)
    hit = int(np.searchsorted(below, draw, side="left"))                              # the first index where draw - sum <= 0
    return int(order[min(hit, kept - 1)])


def norm_loudness(samples) -> tuple[np.ndarray, float]:
    """The recording brought to TARGET_LUFS (RMS stands in for integrated loudness), and the gain in dB. Silence is left alone."""
    x = np.asarray(samples, dtype=np.float32)
    rms = float(np.sqrt(np.sum(x * x, dtype=np.float32) / max(len(x), 1)))
    if rms <= 1e-6:
        return x.copy(), 0.0
    gain_db = TARGET_LUFS - 20.0 * float(np.log10(rms))
    gain = 10.0 ** (gain_db / 20.0)
    if not np.isfinite(gain) or gain <= 0:
        return x.copy(), 0.0
    return np.clip(x * np.float32(gain), -1.0, 1.0), gain_db


def punc_norm(text: str) -> str:
    """The text as the model saw its training data (Resemble's punc_norm): a capital, single spaces, plain punctuation, something to end on."""
    text = " ".join(text.split())
    if not text:
        return text
    if text[0].islower():
        text = text[0].upper() + text[1:]
    for a, b in (("…", ", "), (":", ","), ("—", "-"), ("–", "-"), (" ,", ","), ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")):
        text = text.replace(a, b)
    text = " ".join(text.split())
    return text if text[-1] in ".!?-," else text + "."


def spoken(generated) -> list[int]:
    """The speech in a written sequence: without the start token, and without the stop token when it ended on one."""
    body = list(generated[1:])
    return body[:-1] if body and body[-1] == STOP_SPEECH_TOKEN else body


def with_prompt(prompt, tokens) -> list[int]:
    """What the decoder reads: the recording's own tokens, the written ones, then three of silence so the sound ends rather than stops."""
    return list(prompt) + list(tokens) + [SILENCE_TOKEN] * 3


def chunks(text: str) -> list[str]:
    """`text` as the chunks it is read in: sentences, joined up to CHUNK_CHARS each. A dot inside a number is not an end; a line break always is."""
    sentences: list[str] = []
    cur = ""
    n = len(text)
    for i, c in enumerate(text):
        cur += c
        nxt = text[i + 1] if i + 1 < n else None
        if c == "\n" or (c in ".!?" and (nxt is None or nxt.isspace())):
            sentences.append(cur)
            cur = ""
    sentences.append(cur)
    out: list[str] = []
    for s in sentences:
        s = " ".join(s.split())
        if not s:
            continue
        if out and len(out[-1]) + 1 + len(s) <= CHUNK_CHARS:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def expected_tokens(chunk: str) -> int:
    """About how many speech tokens `chunk` takes: fifteen characters a second is ordinary narration."""
    return int((len(chunk) / 15.0) * TOKENS_PER_SECOND) + 10


class Voice:
    """What the speech encoder heard in a recording: everything the other networks need to speak in that voice."""

    def __init__(self, features, prompt, embedding, spectrum):
        self.features, self.prompt, self.embedding, self.spectrum = features, prompt, embedding, spectrum


def bundle_dir() -> Path:
    from . import models
    return models.get("chatterbox-turbo").dir


def installed() -> bool:
    from . import models
    return models.ready("chatterbox-turbo")


class Engine:
    """The four networks and the tokenizer, loaded once."""

    def __init__(self, tokenizer, speech_encoder, embed_tokens, language_model, decoder, providers: dict[str, list[str]]):
        self.tokenizer, self.speech_encoder, self.embed_tokens, self.language_model, self.decoder = tokenizer, speech_encoder, embed_tokens, language_model, decoder
        self.providers = providers
        self._voices: dict[tuple, Voice] = {}
        self._lock = threading.Lock()

    @classmethod
    def load(cls, dir: Optional[Path] = None, device: str = "auto") -> "Engine":
        """Loads the bundle. `device`: "auto" (the GPU for the networks that gain from it), "cpu", or "cuda" (all four)."""
        import os

        import onnxruntime as ort
        from tokenizers import Tokenizer

        from . import gpu, models
        d = dir or models.ensure("chatterbox-turbo")
        gpu.prepare()
        threads = max(1, min(8, os.cpu_count() or 1))

        def open_(name: str, cuda: bool) -> "ort.InferenceSession":
            so = ort.SessionOptions()
            so.intra_op_num_threads = threads
            so.log_severity_level = 3                                                       # errors only (CUDA prints warnings about harmless scatter ops)
            prov = gpu.onnx_providers(gpu=cuda)
            return ort.InferenceSession(str(d / "onnx" / name), sess_options=so, providers=prov)

        plan = {"speech_encoder": False, "embed_tokens": False, "language_model": False, "decoder": False}
        if device == "cuda":
            plan = {k: True for k in plan}
        elif device == "auto":
            plan.update(AUTO_CUDA)
        s = {k: open_(f, plan[k]) for k, f in (("speech_encoder", "speech_encoder_quantized.onnx"), ("embed_tokens", "embed_tokens_quantized.onnx"),
                                              ("language_model", "language_model_quantized.onnx"), ("decoder", "conditional_decoder_quantized.onnx"))}
        return cls(Tokenizer.from_file(str(d / "tokenizer.json")), s["speech_encoder"], s["embed_tokens"], s["language_model"], s["decoder"],
                   {k: v.get_providers() for k, v in s.items()})

    # --- hearing -----------------------------------------------------------------------------------------------------------------------------------
    def hear(self, reference: np.ndarray) -> Voice:
        """The speech encoder over the recording (24 kHz mono), brought to the loudness the model was trained at."""
        seconds = len(reference) / SAMPLE_RATE
        if seconds < MIN_REFERENCE_SECONDS:
            raise CloneError(f"the recording is {seconds:.1f}s of sound and Chatterbox needs at least {MIN_REFERENCE_SECONDS:.0f}s of clear speech to take a voice from - pick a longer sample, or start it earlier")
        ref, _ = norm_loudness(reference)
        key = (len(ref), float(ref[::997].sum()), float(np.abs(ref).sum()))
        with self._lock:
            if key in self._voices:
                return self._voices[key]
            o = self.speech_encoder.run(None, {"audio_values": ref.reshape(1, -1).astype(np.float32)})
            names = [x.name for x in self.speech_encoder.get_outputs()]
            got = dict(zip(names, o))
            v = Voice(got["audio_features"].astype(np.float32), got["audio_tokens"].reshape(-1).astype(np.int64).tolist(),
                      got["speaker_embeddings"].astype(np.float32), got["speaker_features"].astype(np.float32))
            if len(self._voices) > 8:
                self._voices.clear()
            self._voices[key] = v
            return v

    # --- writing -----------------------------------------------------------------------------------------------------------------------------------
    def _embed(self, ids) -> np.ndarray:
        return self.embed_tokens.run(None, {"input_ids": np.asarray(ids, dtype=np.int64).reshape(1, -1)})[0].astype(np.float32)

    def write(self, chunk: str, voice: Voice, cancel: Optional[threading.Event] = None, progress: Optional[Callable[[int], None]] = None, rng: Optional[Rng] = None) -> list[int]:
        """The language model over one chunk: the speech tokens it writes, without the start and stop tokens."""
        text_ids = list(self.tokenizer.encode(chunk, add_special_tokens=True).ids)
        if all(i == TEXT_END_TOKEN for i in text_ids):
            return []
        embeds = np.concatenate([voice.features, self._embed(text_ids)], axis=1)               # [1, T + n, width]
        seq_len = embeds.shape[1]
        prompt_len = seq_len
        position = 0
        out_names = [x.name for x in self.language_model.get_outputs()]
        cache: list[Optional[np.ndarray]] = [None] * (LAYERS * 2)
        generated = [START_SPEECH_TOKEN]
        rng = rng or Rng.seeded()
        limit = min(MAX_NEW_TOKENS, expected_tokens(chunk) * RUNAWAY + 64)
        empty = np.zeros((1, KV_HEADS, 0, HEAD_DIM), dtype=np.float32)
        past_names = [f"past_key_values.{layer}.{kind}" for layer in range(LAYERS) for kind in ("key", "value")]
        present_names = [f"present.{layer}.{kind}" for layer in range(LAYERS) for kind in ("key", "value")]
        for step in range(limit):
            if cancel is not None and cancel.is_set():
                raise Cancelled("speech generation cancelled")
            total = prompt_len + step
            feed = {"inputs_embeds": embeds, "attention_mask": np.ones((1, total), dtype=np.int64),
                    "position_ids": np.arange(position, position + seq_len, dtype=np.int64).reshape(1, -1)}
            for i, n in enumerate(past_names):
                feed[n] = cache[i] if cache[i] is not None else empty
            outs = dict(zip(out_names, self.language_model.run(None, feed)))
            logits = outs["logits"][0, -1]
            nxt = sample_token(logits, generated, REPETITION_PENALTY, TEMPERATURE, TOP_K, TOP_P, rng)
            for i, n in enumerate(present_names):
                cache[i] = outs[n]
            generated.append(nxt)
            if progress:
                progress(step + 1)
            if nxt == STOP_SPEECH_TOKEN:
                break
            position += seq_len
            embeds = self._embed([nxt])
            seq_len = 1
        return spoken(generated)

    # --- decoding ----------------------------------------------------------------------------------------------------------------------------------
    def decode(self, voice: Voice, tokens) -> np.ndarray:
        """The decoder over the recording's tokens, the written ones and a beat of silence: sound at 24 kHz."""
        allt = np.asarray(with_prompt(voice.prompt, tokens), dtype=np.int64).reshape(1, -1)
        out = self.decoder.run(None, {"speech_tokens": allt, "speaker_embeddings": voice.embedding, "speaker_features": voice.spectrum})
        names = [x.name for x in self.decoder.get_outputs()]
        return np.asarray(dict(zip(names, out))["waveform"], dtype=np.float32).reshape(-1)

    # --- speaking ----------------------------------------------------------------------------------------------------------------------------------
    def speak(self, text: str, reference: np.ndarray, cancel: Optional[threading.Event] = None, progress: Optional[Callable[[float], None]] = None, seed: Optional[int] = None) -> np.ndarray:
        """`text` in the voice of `reference` (mono, 24 kHz): samples at SAMPLE_RATE. Long text is read a chunk at a time with a short gap between."""
        voice = self.hear(np.asarray(reference, dtype=np.float32))
        parts = chunks(punc_norm(text))
        if not parts:
            raise CloneError("nothing to say: the text is empty")
        expected = sum(expected_tokens(c) for c in parts)
        rng = Rng(seed) if seed is not None else Rng.seeded()
        written = 0
        out: list[np.ndarray] = []
        for i, c in enumerate(parts):
            if i:
                out.append(np.zeros(int(SAMPLE_RATE * GAP_SECONDS), dtype=np.float32))
            base = written
            toks = self.write(c, voice, cancel, (lambda n, base=base: progress(min((base + n) / max(expected, 1), 0.95))) if progress else None, rng)
            written += len(toks)
            out.append(self.decode(voice, toks))
        if progress:
            progress(1.0)
        return np.concatenate(out)


# which networks run on the GPU in "auto" mode; set by measurement (see plan.md, P7 step 3.6e)
AUTO_CUDA: dict[str, bool] = {"speech_encoder": True, "embed_tokens": True, "language_model": True, "decoder": True}
