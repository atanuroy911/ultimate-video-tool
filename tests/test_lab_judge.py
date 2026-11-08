"""D1's CLI and thresholds. No renderer, AI, recognition or server is started."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from vt import lab_judge as J
from vt.util import write_json


@pytest.fixture()
def judged(tmp_path):
    data = tmp_path / "data"
    folder = data / "projects" / "fixture"
    comp = folder / "composition" / J.FORMATS["1:1"]["tag"]
    comp.mkdir(parents=True)
    (folder / "exports").mkdir()
    video = folder / "exports" / f"fixture-{comp.name}-finished.mp4"
    video.write_bytes(b"a fixture stub, never decoded")
    (folder / "exports" / ".render-1x1.mp4").write_bytes(b"an unfinished export")
    write_json(folder / "project.json", {"id": "fixture", "aspect": "9:16", "director": {"who": "claude@laptop"}})
    (folder / "ai_talk.jsonl").write_text('{"who":"claude-pc","model":""}\n{"who":"claude-pc","model":"sonnet"}\n', encoding="utf-8")
    write_json(comp / "data.json", {"scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 6}]})
    (comp / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return data, folder, video, comp


def _frames(monkeypatch, comp, *, bad=False):
    def measure(actual_comp, times):
        assert actual_comp == comp
        assert times == [0.0, 1.0, 4.0]
        result = {time: {"coveredFaces": [], "outside": [], "subject": True} for time in times}
        if bad:
            result[0.0]["subject"] = False
            result[1.0]["coveredFaces"] = [{"by": "tag", "face": "Maya", "percent": 10.2}]
            result[4.0]["outside"] = ["label"]
        else:
            result[1.0]["coveredFaces"] = [{"by": "tag", "face": "Maya", "percent": 10.0}]
        return result

    monkeypatch.setattr(J, "frame_acceptance", measure)


@pytest.mark.parametrize("bad", [False, True])
def test_cli_checks_an_existing_fixture_and_returns_failure_on_any_bad_row(judged, monkeypatch, capsys, bad):
    data, folder, video, comp = judged
    _frames(monkeypatch, comp, bad=bad)
    if bad:
        with (folder / "ai_talk.jsonl").open("a", encoding="utf-8") as stream:
            stream.write('{"who":"ollama"}\n')
        write_json(folder / "ai_notice.json", {"message": "Local AI finished the video after Claude timed out."})
    monkeypatch.setattr(J.craft, "check", lambda p: {"score": 80, "violations": [
        {"severity": "major" if bad else "minor", "says": "An opening element is hard to see."}
    ]})

    def retention(actual_video, aspect, composition, audio):
        assert actual_video == video and aspect == "1:1" and len(composition["scenes"]) == 2 and audio is None
        return {"risk": 16 if bad else 15}

    def judge(project, actual_video, *, persist):
        assert actual_video == video and persist is False
        return {"passed": not bad, "failed": ["loudness"] if bad else [], "skipped": ["duration"],
                "verdicts": [{"judge": "loudness", "value": {"lufs": -17.0 if bad else -16.0}}]}

    def ffmpeg(args, **kwargs):
        assert str(video) in args and "blackdetect=d=0.1:pix_th=0.12" in args
        assert args[args.index("-hwaccel") + 1] == "none"
        return SimpleNamespace(returncode=0, stderr="black_start:1.2 black_end:1.4 black_duration:0.2" if bad else "")

    monkeypatch.setattr(J.retention, "scorecard", retention)
    monkeypatch.setattr(J, "judge_export", judge)
    monkeypatch.setattr(J, "find_tool", lambda _: "ffmpeg")
    monkeypatch.setattr(J.subprocess, "run", ffmpeg)
    before = {path.relative_to(folder): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    assert J.main(["fixture", "--data", str(data)]) == int(bad)
    report = capsys.readouterr().out
    assert report.count("FAIL  " if bad else "PASS  ") == (10 if bad else 11)          # the fixture has no cartoon scene: "One picture at a time" passes either way
    assert "first three seconds" in report and "contact sheet" in report
    if bad:
        assert "10.20%" in report and "4.00 s" in report and "1.2 s for 0.2 s" in report
    assert before == {path.relative_to(folder): path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def test_missing_measurements_fail_closed(judged, monkeypatch):
    _, folder, video, comp = judged
    monkeypatch.setattr(J, "frame_acceptance", lambda *_: {0.0: {"subject": True, "coveredFaces": [], "outside": []}})
    assert not any(check.passed for check in J._frame_checks(comp, {"scenes": [{"start": 0, "end": 1}]}))
    monkeypatch.setattr(J, "judge_export", lambda *a, **kw: {"passed": True, "failed": [], "skipped": ["loudness"], "verdicts": []})
    automatic, loudness = J._automatic(J.Project(folder.name, folder.parent), video)
    assert automatic.passed and not loudness.passed


def test_a_decode_error_cannot_be_mistaken_for_no_black_flashes(monkeypatch):
    monkeypatch.setattr(J, "find_tool", lambda _: "ffmpeg")
    monkeypatch.setattr(J.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr=""))
    passed, detail = J._blackdetect(Path("damaged.mp4"))
    assert not passed and "decode" in detail


@pytest.mark.parametrize("name", ["../outside.mp4", "..\\outside.mp4", "C:outside.mp4"])
def test_cannot_judge_an_export_outside_this_project(judged, capsys, name):
    data, *_ = judged
    assert J.main(["fixture", "--data", str(data), "--file", name]) == 1
    assert "FAIL  Project and export" in capsys.readouterr().out


def test_studio_judge_still_saves_while_the_lab_can_check_read_only(judged, monkeypatch):
    from vt import judges
    from vt.server.review_routes import judge_export
    from vt.util import read_json

    _, folder, video, comp = judged
    project = J.Project(folder.name, folder.parent)
    write_json(project.beats_path, {"beats": []})
    write_json(project.transcript_path, {"language": "en", "words": []})
    sidecar = video.with_suffix(".judges.json")

    def measure(selected, *, words, scenes, composition, kind):
        assert selected == video and composition == read_json(comp / "data.json")
        return {"passed": False, "failed": ["loudness"], "skipped": [], "verdicts": []}

    monkeypatch.setattr(judges, "judge_video", measure)
    assert not judge_export(project, video, persist=False)["passed"]
    assert not sidecar.exists()
    assert read_json(sidecar) is None
    assert judge_export(project, video) == read_json(sidecar)


def test_the_judge_fails_a_cartoon_whose_pictures_pile_up():
    from vt.lab_judge import _one_picture

    piled = {"scenes": [{"id": "s2", "start": 4.52, "end": 10.86, "stick": {"x": 1}, "elements": [
        {"type": "sticker", "at": 4.79, "label": "Every morning"}, {"type": "icon", "at": 5.99, "label": "The shop"}]}]}
    ok, says = _one_picture(piled)
    assert not ok and "Every morning and The shop" in says
    paged = {"scenes": [{"id": "s2", "start": 4.52, "end": 5.99, "stick": {"x": 1}, "elements": [{"type": "sticker", "at": 4.79}]},
                        {"id": "s2p2", "start": 5.99, "end": 10.86, "stick": {"x": 1}, "elements": [{"type": "icon", "at": 5.99}, {"type": "keyword", "at": 6.1}]}]}
    assert _one_picture(paged)[0]


def test_a_figure_walking_in_may_cross_the_edge():
    from vt.lab_judge import _crossing

    comp = {"scenes": [{"id": "s2", "stick": {"cast": [{"id": "maya", "name": "Maya"}],
                                              "actions": [{"who": "maya", "do": "walk_in", "start": 4.62, "end": 6.02}, {"who": "maya", "do": "point", "start": 7.2, "end": 8.1}]}}]}
    assert _crossing(comp, "Maya", 5.29)
    assert not _crossing(comp, "Maya", 7.5)                       # standing cut off while pointing still fails
    assert not _crossing(comp, "Mother", 5.29)
