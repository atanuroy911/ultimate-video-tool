from vt import tighten as TG


def beats(lengths):
    out, t = [], 0.0
    for i, d in enumerate(lengths):
        out.append({"id": f"b{i + 1}", "start": t, "end": t + d, "text": f"sentence {i + 1}"})
        t += d
    return out


def test_target_only_for_long_vertical_videos_unless_asked():
    assert TG.target_seconds("auto", "9:16", 120) == 60 and TG.target_seconds("auto", "9:16", 80) is None
    assert TG.target_seconds("auto", "16:9", 300) is None
    assert TG.target_seconds("90", "16:9", 120) == 90 and TG.target_seconds("keep", "9:16", 500) is None


def test_drops_filler_first_and_protects_hook_point_cta_and_dependencies():
    b = beats([10] * 10)                                      # 100 s
    s = {f"b{i}": {"role": "claim", "importance": 1} for i in range(1, 11)}
    s["b1"] = {"role": "hook", "importance": 0}               # the opening is never dropped, even if rated filler
    s["b3"] = {"role": "claim", "importance": 0}
    s["b4"] = {"role": "recap", "importance": 1}
    s["b5"] = {"role": "claim", "importance": 3}
    s["b6"] = {"role": "claim", "importance": 0}
    s["b7"] = {"role": "example", "importance": 1, "relation": "explains", "rel_to": "b6"}   # b6 is needed by b7
    s["b10"] = {"role": "cta", "importance": 0}
    out = TG.choose(b, s, 80)
    ids = [d["beat"] for d in out]
    assert ids == ["b3", "b4"] and "filler" in out[0]["reason"] and "repeats" in out[1]["reason"]
    assert not {"b1", "b5", "b6", "b10"} & set(TG.choose(b, s, 10) and [d["beat"] for d in TG.choose(b, s, 10)])


def test_never_drops_more_than_the_cap():
    b = beats([10] * 10)
    s = {f"b{i}": {"role": "claim", "importance": 0} for i in range(1, 11)}
    assert len(TG.choose(b, s, 5)) == int(10 * TG.MAX_SHARE)


def test_a_story_keeps_its_plot():
    # the owner's English sample (2026-10-23): a parable lost "He took out the watch and came back to his father"
    b = beats([10] * 10)
    s = {f"b{i}": {"role": "story", "importance": 1} for i in range(1, 11)}
    s["b4"] = {"role": "claim", "importance": 0}
    texts = ["Once upon a time, there lived a man in a small village.", "He had a lazy son."] + ["The man said, go to the market."] * 8
    assert TG.is_narrative("motivation", {k: {"role": "claim"} for k in s}, texts)
    assert [d["beat"] for d in TG.choose(b, s, 60, narrative=True)] == ["b4"]          # only the filler goes
    assert not TG.is_narrative("finance", {"b1": {"role": "claim"}}, ["Save ten percent.", "Spend less than you earn."])


def test_the_cuts_input_does_not_change_when_tighten_has_nothing_to_drop(projects_dir):
    """The second pipeline run must not redo the cuts: tighten.json appearing with an empty list is not a change (it was, which re-cut every recording once)."""
    from vt.pipeline import tighten_signature
    from vt.project import Project
    from vt.util import write_json

    p = Project("sigtest")
    p.dir.mkdir(parents=True, exist_ok=True)
    before = tighten_signature(p)                                       # tighten has not run: no file
    write_json(p.dir / "tighten.json", {"hash": "abc", "target": None, "cuts": []})
    assert tighten_signature(p) == before                               # ran, nothing to drop
    write_json(p.dir / "tighten.json", {"hash": "abc", "target": 60.0, "cuts": [{"beat": "b3", "src": [[4.0, 6.5]]}]})
    assert tighten_signature(p) != before                               # a real drop does change it
    write_json(p.dir / "tighten.json", {"hash": "different", "target": 60.0, "cuts": [{"beat": "b3", "src": [[4.0, 6.5]]}]})
    assert tighten_signature(p) == tighten_signature(p)
