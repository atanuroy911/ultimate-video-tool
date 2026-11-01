from vt.schema import Cuts
from vt.stages import terms, words as W
from vt.stages.align import snap_words


def w(text, s, e, conf=1.0):
    return {"text": text, "start": s, "end": e, "conf": conf}


# ---------------------------------------------------------------- snapping to real speech
def test_word_before_a_pause_stops_where_the_speech_stops():
    # attention alignment stretched "কি" across the whole pause; the next word starts at the speech onset
    out, dropped = snap_words([w("কি", 0.70, 1.88), w("ধরুন", 1.88, 2.28)], [(0.95, 1.90)])
    assert dropped == 0
    assert 0.95 <= out[0]["end"] <= 1.05                      # clipped to the speech end (+ tail)
    assert abs(out[1]["start"] - 1.88) < 0.03                 # onset unchanged


def test_trailing_hallucination_is_dropped():
    out, dropped = snap_words([w("ইয়েল্ড", 13.26, 13.50), w("থেরা", 13.50, 14.38, conf=0.55)], [(13.54, 14.40)], duration=14.4)
    assert [x["text"] for x in out] == ["ইয়েল্ড"] and dropped == 1


def test_burst_of_hallucinated_words_at_the_end_is_removed():
    """Seen on real output: after the last real word, the model emitted a news-style sentence with ~zero-length timestamps."""
    words = [w("নেট", 12.95, 13.27), w("ইয়েল্ড", 13.27, 13.49)] + [
        w(t_, 13.49, 13.49 + i * 0.02, conf=0.7) for i, t_ in enumerate(["ছেলেটির", "প্রতিদিন", "রাজ্যের", "নির্বাচনে", "জানান"])]
    out, dropped = snap_words(words, [(13.54, 14.40)], duration=14.4)
    assert [x["text"] for x in out] == ["নেট", "ইয়েল্ড"] and dropped == 5


def test_word_entirely_inside_a_pause_is_dropped_but_confident_real_words_survive():
    out, dropped = snap_words([w("ক", 0.0, 0.5), w("ভূত", 1.2, 1.5, conf=0.4), w("খ", 2.5, 3.0, conf=0.5)], [(1.0, 2.4)])
    assert [x["text"] for x in out] == ["ক", "খ"] and dropped == 1     # "খ" is low-confidence but long enough to be real


def test_impossibly_fast_long_word_is_dropped_even_when_confident():
    # 16 characters in 60 ms after the speech has ended (seen on real output) cannot have been spoken
    out, dropped = snap_words([w("যায়", 13.1, 13.3), w("বিশ্ববিদ্যালয়ের", 13.34, 13.40, conf=0.87)], [])
    assert [x["text"] for x in out] == ["যায়"] and dropped == 1
    out, dropped = snap_words([w("হয়ে", 1.0, 1.08), w("পঞ্চাশ", 2.0, 2.34)], [])
    assert len(out) == 2 and dropped == 0                        # short real words are safe


def test_snapping_never_creates_overlaps_or_negative_lengths():
    out, _ = snap_words([w("এক", 0.0, 1.0), w("দুই", 0.9, 1.4), w("তিন", 1.3, 2.0)], [(0.5, 0.95)])
    for a, b in zip(out, out[1:]):
        assert a["end"] <= b["start"] + 1e-9
    assert all(x["end"] > x["start"] for x in out)


# ---------------------------------------------------------------- Banglish script policy
def test_mixed_policy_writes_english_terms_in_latin_letters():
    assert terms.to_policy("ফ্ল্যাট", "mixed") == "flat"
    assert terms.to_policy("ইয়েল্ড।", "mixed") == "yield।"            # punctuation preserved
    assert terms.to_policy("ফ্ল্যাটের", "mixed") == "flat-এর"          # suffix stays attached, as an independent letter (a vowel sign after Latin renders as ◌)
    assert terms.to_policy("টাকা", "mixed") == "টাকা"                  # ordinary Bangla untouched
    assert terms.to_policy("hello", "mixed") == "hello"


def test_bangla_policy_writes_english_terms_in_bangla_script():
    assert terms.to_policy("flat", "bangla") == "ফ্ল্যাট"
    assert terms.to_policy("Net,", "bangla") == "নেট,"
    assert terms.to_policy("flat-এর", "bangla") == "ফ্ল্যাটের"
    assert terms.to_policy("unknownword", "bangla") == "unknownword"


def test_explicit_glossary_and_edits_beat_the_policy():
    raw = {"words": [{"text": "ফ্ল্যাট", "start": 0, "end": 0.5, "conf": 1}, {"text": "নেট", "start": 0.6, "end": 1.0, "conf": 1}]}
    cuts = Cuts(source_duration=2, keep=[(0, 2)])
    tr = W.build_transcript(raw, cuts, {"ফ্ল্যাট": "অ্যাপার্টমেন্ট"}, policy="mixed")
    assert [x.text for x in tr.words] == ["অ্যাপার্টমেন্ট", "net"]
    tr = W.build_transcript(raw, cuts, policy="mixed", edits={"w2": {"text": "নেট"}})
    assert [x.text for x in tr.words] == ["flat", "নেট"]
    tr = W.build_transcript(raw, cuts, policy="bangla")
    assert [x.text for x in tr.words] == ["ফ্ল্যাট", "নেট"]
    assert tr.words[0].lang == "bn"
    assert W.build_transcript(raw, cuts, policy="mixed").words[0].lang == "en"   # language tag follows the final text


def test_terms_match_regardless_of_unicode_encoding_of_the_same_letter():
    """Regression: the model emits য় as one code point (U+09DF) while a typed list used য + nukta, so 'ইয়েল্ড' never matched."""
    composed = "ইয়েল্ড"           # য় as a single code point
    decomposed = "ইয়েল্ড"         # য + nukta
    assert composed != decomposed
    assert terms.to_policy(composed, "mixed") == "yield"
    assert terms.to_policy(decomposed, "mixed") == "yield"
    assert terms.to_policy(composed + "।", "mixed") == "yield।"
    # an explicit glossary entry typed in one form matches the other
    assert W.apply_glossary(composed, {decomposed: "ইল্ড"}) == "ইল্ড"


def test_confident_long_word_in_a_noisy_room_is_never_dropped():
    """Regression (real recording): quiet speech fell under a noisy threshold; 'তখন' (p=1.00, 0.9 s) was thrown away."""
    out, dropped = snap_words([w("তখন", 5.43, 6.37, conf=1.0), w("বলে", 6.4, 6.7)], [(5.40, 6.40)])
    assert [x["text"] for x in out] == ["তখন", "বলে"] and dropped == 0
    # but a zero-length junk word of middling confidence in the same silence still goes
    out, dropped = snap_words([w("প্রেসিডেন্টের", 5.9, 5.9, conf=0.9)], [(5.40, 6.40)])
    assert out == [] and dropped == 1


def test_vowel_sign_after_a_latin_word_becomes_an_independent_letter():
    """Regression (real render): 'marketে' showed a dotted circle because a dependent vowel sign cannot follow a Latin letter."""
    assert W.fix_latin_vowel_sign("সেই marketে চলে flatের") == "সেই market-এ চলে flat-এর"
    assert W.fix_latin_vowel_sign("টাকা দাম") == "টাকা দাম"                  # ordinary Bangla untouched
    assert terms.join_latin_suffix("tax", "ের") == "tax-এর" and terms.join_latin_suffix("tax", "কে") == "taxকে"


def test_a_soft_first_word_after_a_pause_is_kept_but_junk_in_the_pause_is_not():
    from vt.stages.align import snap_words
    sil = [(30.18, 31.21)]
    w = lambda t, s, e, c: {"text": t, "start": s, "end": e, "conf": c}
    kept, dropped = snap_words([w("state.", 29.5, 29.81, 0.95), w("It", 31.06, 31.26, 0.9), w("is", 31.28, 31.4, 0.99), w("a", 31.4, 31.5, 0.99)], sil, 40.0)
    assert [x["text"] for x in kept] == ["state.", "It", "is", "a"] and dropped == 0
    assert kept[1]["start"] >= 31.05 and kept[1]["end"] <= kept[2]["start"] + 1e-6
    # a hallucination inside the pause (low confidence, nothing spoken right after it) is still removed
    kept, dropped = snap_words([w("state.", 29.5, 29.81, 0.95), w("Thank you.", 30.4, 30.9, 0.35), w("It", 31.5, 31.6, 0.9)], sil, 40.0)
    assert [x["text"] for x in kept] == ["state.", "It"] and dropped == 1
    # a confident word in the middle of the pause (not at its end) is not a leading word either
    kept, dropped = snap_words([w("state.", 29.5, 29.81, 0.95), w("hmm", 30.5, 30.8, 0.9), w("It", 31.5, 31.6, 0.9)], sil, 40.0)
    assert [x["text"] for x in kept] == ["state.", "It"]


def test_an_unsure_word_in_the_middle_of_speech_is_kept():
    from vt.stages.align import snap_words
    w = lambda t, s, e, c: {"text": t, "start": s, "end": e, "conf": c}
    kept, dropped = snap_words([w("is", 75.99, 76.13, 1.0), w("three", 76.13, 76.27, 0.23), w("thousand", 76.27, 76.53, 1.0)], [(70.0, 70.5), (80.0, 81.0)], 90.0)
    assert [x["text"] for x in kept] == ["is", "three", "thousand"] and dropped == 0
