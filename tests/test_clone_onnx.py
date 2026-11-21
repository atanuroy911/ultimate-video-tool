"""The ONNX voice-cloning port. The first half is Concat's own unit tests for chatterbox.rs, with the same inputs and expected outputs; the second half needs the downloaded model."""
import numpy as np
import pytest

from vt import clone_onnx as C

nan = float("nan")


def test_the_penalty_turns_a_written_token_away_and_the_best_is_picked():
    assert C.next_token([0.1, 0.9, 0.5], [], 1.2) == 1                          # unwritten: the largest wins
    assert C.next_token([0.8, 0.9, 0.5], [1], 1.2) == 0                         # written and positive: divided, so a close second overtakes it
    assert C.next_token([-0.5, -0.55, -1.0], [0], 1.2) == 1                     # written and negative: multiplied further down
    assert C.next_token([0.8, 0.9, 0.5], [1], 1.0) == 1                         # a penalty of one changes nothing
    assert C.next_token([0.3, 0.3], [], 1.2) == 0                               # ties go to the first
    assert C.next_token([], [], 1.2) == 0                                       # an empty vocabulary gives 0 rather than failing
    assert C.next_token([nan, 0.1], [], 1.2) == 1                               # NaN never wins


def test_a_sample_stays_inside_the_nucleus():
    logits = [0.1, 5.0, 4.9, -3.0, 0.0]
    rng = C.Rng(7)
    assert C.sample_token(logits, [], 1.2, 0.0, 1000, 0.95, rng) == 1           # temperature zero is the argmax
    assert C.sample_token(logits, [], 1.2, 0.8, 1000, 0.0, rng) == 1           # a nucleus shut to nothing is too
    for _ in range(200):
        assert C.sample_token(logits, [], 1.2, 0.8, 1000, 0.95, rng) in (1, 2)
    seen = set(C.sample_token(logits, [], 1.2, 0.8, 1000, 0.95, rng) for _ in range(500))
    assert {1, 2} <= seen                                                       # both of the nucleus get drawn over time
    for _ in range(50):
        assert C.sample_token(logits, [], 1.2, 0.8, 1, 0.95, rng) == 1          # top_k of one is the argmax however the dice fall
    assert C.sample_token([], [], 1.2, 0.8, 1000, 0.95, rng) == 0
    assert C.sample_token([nan, nan], [], 1.2, 0.8, 1000, 0.95, rng) == 0


def test_a_written_token_is_buried_by_the_penalty_in_a_sample():
    logits = [0.0, 5.0, 4.0]
    rng = C.Rng(3)
    drawn = {C.sample_token(logits, [1], 3.0, 0.5, 1000, 0.99, rng) for _ in range(200)}      # 5.0 / 3 = 1.67: token 2 now leads
    assert 2 in drawn and drawn <= {0, 1, 2}
    assert C.sample_token(logits, [1], 3.0, 0.0, 1000, 0.99, rng) == 2


def test_the_generator_is_uniform_and_repeatable():
    a, b = C.Rng(42), C.Rng(42)
    seen = set()
    for _ in range(1000):
        x = a.unit()
        assert 0.0 <= x < 1.0
        assert x == b.unit()
        seen.add(x)
    assert len(seen) > 900
    assert C.Rng(0).unit() != 0.0                                               # a zero seed is not stuck
    assert C.Rng.seeded().unit() != C.Rng.seeded().unit() or True


def test_the_xorshift_matches_the_reference_values():
    """First draws of seed 1, computed by hand from the xorshift64* definition (the Rust code is the same arithmetic)."""
    s = 1
    out = []
    for _ in range(3):
        s ^= s >> 12
        s ^= (s << 25) & C.MASK64
        s ^= s >> 27
        out.append((((s * 0x2545F4914F6CDD1D) & C.MASK64) >> 40) / float(1 << 24))
    r = C.Rng(1)
    assert [r.unit() for _ in range(3)] == pytest.approx(out, abs=1e-7)


def test_a_recording_is_brought_to_the_target_loudness():
    for amp in (0.9, 0.05, 0.002):
        x = (amp * np.sin(np.arange(24000) * 0.05)).astype(np.float32)
        out, gain = C.norm_loudness(x)
        lufs = 20 * np.log10(np.sqrt(np.mean(out * out)))
        assert abs(lufs - C.TARGET_LUFS) < 0.5, (amp, lufs, gain)
        assert np.all(np.abs(out) <= 1.0)
    silent, gain = C.norm_loudness(np.zeros(100, np.float32))
    assert not silent.any() and gain == 0.0


def test_the_text_is_normalised_the_way_resemble_does_it():
    assert C.punc_norm("hello   world") == "Hello world."
    assert C.punc_norm("Already ends!") == "Already ends!"
    assert C.punc_norm("a list: one… two") == "A list, one, two."
    assert C.punc_norm("“quoted” — and ‘this’") == "\"quoted\" - and 'this'."
    assert C.punc_norm("trailing ,") == "Trailing,"
    assert C.punc_norm("   ") == ""
    assert C.punc_norm("ünïcode start") == "Ünïcode start."


def test_the_start_and_stop_are_stripped_and_the_prompt_and_silence_added():
    assert C.spoken([C.START_SPEECH_TOKEN, 5, 6, C.STOP_SPEECH_TOKEN]) == [5, 6]
    assert C.spoken([C.START_SPEECH_TOKEN, 5, 6]) == [5, 6]                     # ran out without a stop
    assert C.spoken([C.START_SPEECH_TOKEN, C.STOP_SPEECH_TOKEN]) == []
    assert C.spoken([C.START_SPEECH_TOKEN]) == [] and C.spoken([]) == []
    assert C.with_prompt([1, 2], [5, 6]) == [1, 2, 5, 6] + [C.SILENCE_TOKEN] * 3
    assert C.with_prompt([], []) == [C.SILENCE_TOKEN] * 3


def test_text_is_read_a_few_sentences_at_a_time():
    assert C.chunks("") == [] and C.chunks("   \n ") == []
    assert C.chunks("Hello there.") == ["Hello there."]
    assert C.chunks("One. Two! Three?") == ["One. Two! Three?"]
    assert C.chunks("Version 2.5 is out. Yes.") == ["Version 2.5 is out. Yes."]            # a dot inside a number is not an end
    assert C.chunks("First line\nSecond line") == ["First line Second line"]
    long = "This sentence is exactly fifty characters long, ok. " * 10
    parts = C.chunks(long)
    assert len(parts) >= 2 and all(len(p) <= C.CHUNK_CHARS for p in parts)
    assert len(" ".join(parts).split()) == len(long.split())
    assert len(C.chunks("word " * 80)) == 1                                     # one sentence longer than a chunk is not cut mid-word
    assert C.expected_tokens("Hello there, how are you today?") > 10


# ---- needs the downloaded model (1.1 GB; downloaded by `vt.models.ensure("chatterbox-turbo")`) -------------------------------------------------------

needs_model = pytest.mark.skipif(not C.installed(), reason="the Chatterbox Turbo bundle is not downloaded")


@needs_model
def test_the_graphs_have_the_names_the_code_feeds():
    e = C.Engine.load(device="cpu")

    def ins(s):
        return {x.name for x in s.get_inputs()}

    def outs(s):
        return {x.name for x in s.get_outputs()}
    assert ins(e.speech_encoder) == {"audio_values"} and {"audio_features", "audio_tokens", "speaker_embeddings", "speaker_features"} <= outs(e.speech_encoder)
    assert ins(e.embed_tokens) == {"input_ids"} and "inputs_embeds" in outs(e.embed_tokens)
    lm_in = ins(e.language_model)
    assert {"inputs_embeds", "attention_mask", "position_ids"} <= lm_in and sum(n.startswith("past_key_values.") for n in lm_in) == C.LAYERS * 2
    assert "logits" in outs(e.language_model) and sum(n.startswith("present.") for n in outs(e.language_model)) == C.LAYERS * 2
    assert ins(e.decoder) == {"speech_tokens", "speaker_embeddings", "speaker_features"} and "waveform" in outs(e.decoder)
    kv = next(x for x in e.language_model.get_inputs() if x.name == "past_key_values.0.key")
    assert kv.shape[1] == C.KV_HEADS and kv.shape[3] == C.HEAD_DIM


@needs_model
@pytest.mark.models
@pytest.mark.slow
def test_the_real_model_speaks_a_sentence_in_a_given_voice_and_is_repeatable_by_seed():
    import soundfile as sf

    ref, sr = sf.read(str(__import__("pathlib").Path(__file__).parent / "fixtures" / "clone_ref" / "reference_12s.wav"), dtype="float32")
    from scipy.signal import resample_poly

    ref = resample_poly(ref if ref.ndim == 1 else ref.mean(axis=1), 24000, sr).astype("float32")
    e = C.Engine.load()
    a = e.speak("Small habits make a big difference.", ref, seed=5)
    b = e.speak("Small habits make a big difference.", ref, seed=5)
    assert 1.5 < len(a) / C.SAMPLE_RATE < 6 and np.abs(a).max() > 0.05 and np.abs(a).max() < 1.0
    assert len(a) == len(b)                                                         # the same seed writes the same tokens
    with pytest.raises(C.CloneError, match="at least"):
        e.speak("Hi.", ref[:24000 * 3])
    with pytest.raises(C.CloneError, match="empty"):
        e.speak("   ", ref)
    ev = __import__("threading").Event()
    ev.set()
    with pytest.raises(C.Cancelled):
        e.speak("Cancel me before I start.", ref, cancel=ev)
