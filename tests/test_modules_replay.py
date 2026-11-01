from vt.modules.executor import Executor
from vt.modules.replay import replay


def test_replay_rebuilds_pure_artifact_without_ai(tmp_path):
    executor = Executor(tmp_path)
    executor.ws.put_json("transcript.raw", {"words": []}, call_id="seed")
    first = executor.call("audio.find_retakes", why="Check the opening")
    (tmp_path / "retakes.json").unlink()
    results = replay(tmp_path)
    assert first.ok
    assert results[0]["module"] == "audio.find_retakes"
    assert executor.ws.ref("audio.retakes")["hash"] == first.artifacts[0]["hash"]
