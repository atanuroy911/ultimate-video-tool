import json

from vt.modules.calls import append_call, append_technical


def test_call_order_and_technical_redaction(tmp_path):
    append_call(tmp_path, {"module": "one", "plain": "First.", "token": "private",
                           "fix": "try api_key=private"})
    append_call(tmp_path, {"module": "two", "plain": "Second."})
    entries = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [e["seq"] for e in entries] == [1, 2]
    assert entries[0]["token"] == "[redacted]"
    assert "private" not in entries[0]["fix"]
    append_technical(tmp_path, "normal\napi_key=private\nthird", max_lines=2)
    assert (tmp_path / "technical.log").read_text().splitlines() == ["api_key=[redacted]", "third"]


def test_logged_warnings_during_a_call_reach_the_technical_log(tmp_path):
    import logging
    from vt.modules.calls import capture_technical, read_technical

    with capture_technical(tmp_path, "x.y"):
        logging.getLogger("ffmpeg").warning("moov atom not found api_key=abc")
        logging.getLogger("ffmpeg").info("ignored")
    text = read_technical(tmp_path)
    assert "moov atom not found" in text and "abc" not in text and "ignored" not in text
