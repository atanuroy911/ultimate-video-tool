import json

from vt import paths
from vt.util import read_json
from vt.compose import FORMATS, build_caption_chunks, compose_project, resolve_composition, to_srt
from vt.compose.specimen import build_specimen
from vt.project import load_theme
from vt.schema import Word


def W(i, text, s, e):
    return Word(id=f"w{i}", text=text, start=s, end=e)


def test_caption_chunks_break_at_sentences_and_balance_lines():
    ws = [W(1, "ক", 0, .3), W(2, "খ", .35, .6), W(3, "গ।", .65, .9),
          W(4, "অ", 1.0, 1.2), W(5, "আ", 1.25, 1.5), W(6, "তিন", 1.55, 1.8), W(7, "ই", 1.85, 2.1), W(8, "ঈ", 2.15, 2.4),
          W(9, "উ", 2.45, 2.7), W(10, "ঊ", 2.75, 3.0)]          # plain letters: number words would (rightly) be glued to the next word
    chunks = build_caption_chunks(ws, words_per_line=4, max_chars=40, highlight_ids={"w6"})
    texts = [" ".join(w["text"] for w in c["words"]) for c in chunks]
    assert texts[0] == "ক খ গ।"                       # sentence end closes the line
    assert sum(len(c["words"]) for c in chunks[1:]) == 7 and all(2 <= len(c["words"]) <= 3 for c in chunks[1:])  # 2-3 words a line, never 6 + 1
    assert any(w["hl"] for c in chunks for w in c["words"] if w["text"] == "তিন")
    for a, b in zip(chunks, chunks[1:]):
        assert a["end"] <= b["start"] + 1e-6            # captions never overlap


def test_srt_format():
    srt = to_srt([{"start": 0.5, "end": 2.25, "words": [{"text": "হ্যালো"}, {"text": "বিশ্ব"}]}])
    assert srt.startswith("1\n00:00:00,500 --> 00:00:02,250\nহ্যালো বিশ্ব")


def test_resolve_times_are_ordered_and_in_range():
    tr, beats, scenes, dur = build_specimen()
    theme = load_theme("paper")
    icons = read_json(paths.ICONS / "lucide.json")
    for aspect in FORMATS:
        d = resolve_composition(scenes, tr, beats, theme, aspect, dur, icons)
        assert d["format"]["width"] == FORMATS[aspect]["width"]
        starts = [s["start"] for s in d["scenes"]]
        assert starts == sorted(starts) and starts[0] == 0.0
        assert d["scenes"][-1]["end"] == dur
        for s in d["scenes"]:
            assert s["start"] < s["end"]
            for e in s["elements"]:
                assert s["start"] <= e["at"] <= s["end"]
                assert "at_word" not in e
        assert d["captions"] and d["cues"]
        assert d["icons"].get("circle-help")


def test_compose_project_writes_self_contained_folders(ref):
    for aspect, f in FORMATS.items():
        index = compose_project(ref, aspect)
        folder = index.parent
        assert folder.name == f["tag"]
        html = index.read_text(encoding="utf-8")
        assert 'data-composition-id="root"' in html and f'data-width="{f["width"]}"' in html
        assert 'window.__timelines["root"]' in html  # HyperFrames' static contract check looks for this
        for rel in ("runtime/vt.js", "runtime/vt.css", "runtime/gsap.min.js", "fonts/fonts.css", "data.json", "textures/paper-grain.png"):
            assert (folder / rel).exists(), rel
        # fonts referenced by the css exist next to it
        import re
        css = (folder / "fonts" / "fonts.css").read_text(encoding="utf-8")
        for name in re.findall(r"url\(\./([^)]+)\)", css):
            assert (folder / "fonts" / name).exists()
        data = json.loads((folder / "data.json").read_text(encoding="utf-8"))
        assert data["duration"] == ref.cuts().output_duration


def test_script_tag_in_text_cannot_break_out_of_the_page(ref):
    sf = ref.scenes()
    data = sf.model_dump()
    data["scenes"][0]["elements"][0]["text"] = "</script><b>x"
    ref.save_scenes(type(sf).model_validate(data))
    html = compose_project(ref, "9:16").read_text(encoding="utf-8")
    assert html.count("</script>") == html.count("<script")   # every script tag is closed exactly once: the injected </script> is escaped
    assert "<\/script><b>x" in html


def test_square_format_composes_with_its_own_caption_width_and_size(ref):
    from vt.compose import FORMATS
    assert FORMATS["1:1"]["width"] == FORMATS["1:1"]["height"] == 1080 and FORMATS["1:1"]["tag"] == "1x1"
    html = compose_project(ref, "1:1")
    assert html.parent.name == "1x1" and "1080" in html.read_text(encoding="utf-8")
    import json
    data = json.loads((html.parent / "data.json").read_text(encoding="utf-8"))
    assert data["format"]["aspect"] == "1:1" and max(len(" ".join(w["text"] for w in c["words"])) for c in data["captions"]) <= 40
