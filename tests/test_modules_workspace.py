"""Artifact history and invalidation must survive a changed source file."""
from vt.modules.workspace import Workspace


def test_artifact_ref_versions_and_staleness(tmp_path):
    ws = Workspace(tmp_path)
    source = ws.put_json("transcript.raw", {"words": [{"text": "first"}]}, call_id="c1")
    first = ws.put_json("audio.retakes", {"cuts": []}, call_id="c2",
                        inputs={"transcript.raw": source["hash"]})
    assert not ws.stale("audio.retakes")
    ws.put_json("transcript.raw", {"words": [{"text": "second"}]}, call_id="c3")
    assert ws.stale("audio.retakes")
    assert (tmp_path / ".artifact_versions" / "transcript.raw" / f"{source['hash']}.json").exists()
    assert ws.ref("audio.retakes")["hash"] == first["hash"]


def test_audio_input_does_not_count_as_source_video(tmp_path):
    ws = Workspace(tmp_path)
    (tmp_path / "input.wav").write_bytes(b"audio")
    assert ws.exists("source.audio")
    assert not ws.exists("source.video")
    (tmp_path / "input.mp4").write_bytes(b"video")
    assert ws.path_for("source.video").name == "input.mp4"
