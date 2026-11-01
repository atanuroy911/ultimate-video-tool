from vt.retakes import find_retakes


def W(text: str, t0: float = 0.0, gaps: dict[int, float] | None = None) -> list[dict]:
    """Words 0.3 s long, 0.05 s apart; gaps[i] adds a pause before word i."""
    out, t = [], t0
    for i, x in enumerate(text.split()):
        t += (gaps or {}).get(i, 0.0)
        out.append({"text": x, "start": round(t, 3), "end": round(t + 0.3, 3)})
        t += 0.35
    return out


def texts(words, found):
    return [" ".join(words[i]["text"] for i in c["words"]) for c in found]


def test_false_start_is_cut_and_the_full_take_kept():
    w = W("Today I want to today I want to talk about saving money.", gaps={4: 0.8})
    f = find_retakes(w)
    assert texts(w, f) == ["Today I want to"] and "false start" in f[0]["reason"]
    assert f[0]["start"] == w[0]["start"] and f[0]["end"] == w[3]["end"]


def test_whole_sentence_said_twice_keeps_the_last_take():
    w = W("Put away ten percent of your pay. Put away ten percent of what you earn.", gaps={7: 1.0})
    assert texts(w, find_retakes(w)) == ["Put away ten percent of your pay."]


def test_stumble_without_a_pause():
    w = W("It started in the year in the year 2020 with a crash")
    assert texts(w, find_retakes(w)) == ["in the year"]


def test_bangla_false_start():
    w = W("আজ আমি বলব আজ আমি বলব কেন সঞ্চয় দরকার।", gaps={3: 0.7})
    assert texts(w, find_retakes(w)) == ["আজ আমি বলব"]


def test_normal_speech_and_short_rhetorical_repeats_are_kept():
    assert find_retakes(W("Saving is simple. Spend less than you earn. Do it every month.", gaps={3: 0.6, 8: 0.6})) == []
    assert find_retakes(W("Never, never give up.")) == []
    assert find_retakes(W("Step one. Step two. Step three.", gaps={2: 0.6, 4: 0.6})) == []


def test_cuts_stage_removes_the_retake_and_says_why(projects_dir, tmp_path):
    import numpy as np
    import soundfile as sf

    from vt.pipeline import Pipeline
    from vt.project import Project
    from vt.util import read_json, write_json

    wav = tmp_path / "in.wav"
    sf.write(wav, np.zeros(16000 * 8, dtype="float32"), 16000)
    p = Project.create("Retakes", wav, language="en")
    pl = Pipeline(p)
    pl.stage_preprocess()
    words = W("Today I want to today I want to talk about saving money.", t0=0.5, gaps={4: 0.8})
    write_json(p.raw_transcript_path, {"language": "en", "model": "test", "words": words})
    pl.stage_cuts()
    rt = read_json(p.dir / "retakes.json")["cuts"]
    assert len(rt) == 1 and rt[0]["text"] == "Today I want to" and rt[0]["reason"]
    cuts = p.cuts()
    assert cuts.map_time((words[0]["start"] + words[3]["end"]) / 2) is None          # the false start is gone
    assert cuts.map_time((words[4]["start"] + words[4]["end"]) / 2) is not None      # the full take stays

    p.update_meta(options={**p.meta().options.model_dump(), "remove_retakes": False})
    pl.stage_cuts()
    assert read_json(p.dir / "retakes.json")["cuts"] == []


def test_a_spoken_list_is_not_a_false_start():
    # found on the owner's English sample (2026-10-23): "Some said 500," was cut as a false start
    w = W("Some said 500, some said 800, and some said 1000.", gaps={3: 0.6, 6: 0.6})
    assert find_retakes(w) == []


def test_a_cut_off_word_is_still_a_false_start():
    w = W("I want to tal- I want to talk about money.", gaps={4: 0.6})
    assert texts(w, find_retakes(w)) == ["I want to tal-"]


def test_same_words_far_apart_are_not_a_retake():
    w = W("Money is time. " + "filler " * 3 + "Money is time.", gaps={3: 20.0, 6: 1.0})
    assert find_retakes(w) == []
