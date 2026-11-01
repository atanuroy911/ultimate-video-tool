import pytest

from vt import ai
from vt.ai import AIUnavailable, FakeProvider, complete_json, use_provider

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False}


def test_valid_reply_passes():
    p = FakeProvider([{"n": 3}])
    assert complete_json("q", SCHEMA, provider=p) == {"n": 3}


def test_fenced_json_is_accepted():
    p = FakeProvider(['Sure!\n```json\n{"n": 2}\n```'])
    assert complete_json("q", SCHEMA, provider=p) == {"n": 2}


def test_retry_shows_errors_then_succeeds():
    p = FakeProvider([{"n": "x"}, {"n": 1}])
    assert complete_json("q", SCHEMA, provider=p) == {"n": 1}
    assert "previous answer had these problems" in p.calls[1]["prompt"] and "n:" in p.calls[1]["prompt"]


def test_gives_up_after_retry():
    p = FakeProvider(["not json", "still not"])
    with pytest.raises(AIUnavailable):
        complete_json("q", SCHEMA, provider=p)
    assert len(p.calls) == 2


def test_provider_error_propagates():
    p = FakeProvider([AIUnavailable("down")])
    with pytest.raises(AIUnavailable):
        complete_json("q", SCHEMA, provider=p)


def test_repair_hook_runs_before_validation():
    p = FakeProvider([{"n": "4"}])
    assert complete_json("q", SCHEMA, provider=p, repair=lambda d: {"n": int(d["n"])}) == {"n": 4}


def test_images_need_a_vision_provider():
    class Blind(FakeProvider):
        supports_images = False

    with pytest.raises(AIUnavailable):
        complete_json("q", SCHEMA, images=[b"x"], provider=Blind([{"n": 1}]))


def test_use_provider_context_and_cache(tmp_path, monkeypatch):
    from vt import paths

    monkeypatch.setattr(paths, "DATA", tmp_path)

    class Cached(FakeProvider):
        cacheable = True

    p = Cached([{"n": 5}])
    with use_provider(p):
        assert complete_json("q", SCHEMA) == {"n": 5}
        assert complete_json("q", SCHEMA) == {"n": 5}      # second call comes from the cache
    assert len(p.calls) == 1


def test_default_provider_off_when_local_ai_off():
    assert ai.provider_status()["available"] is False
