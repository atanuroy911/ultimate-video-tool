"""A module that names a capability gets an engine resolved before it runs, and the call says which one answered (docs/plans/PLAN-ENGINES-AND-SETUP.MD E7)."""
import json

import pytest
from pydantic import BaseModel

from vt.engines import registry
from vt.modules.executor import Executor
from vt.modules.registry import Cost, module, _REGISTRY


class In(BaseModel):
    pass


class Out(BaseModel):
    ok: bool = True


def make(mid, fallback=None):
    @module(id=mid, version=1, summary="t", when_to_use="t", when_not_to_use="t", inputs=In, outputs=Out, requires=(), produces=(), cost=Cost("instant"), effects="none", determinism="pure",
            grounding=(), fallback=fallback, fallback_reason="t", examples=(), toolboxes=("full",), plain_name="Testing an engine", log_line=lambda i, o: "ran", engines=("image.generate",))
    def run(ws, inputs):
        return Out()


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for k in [k for k in _REGISTRY if k.startswith("zz.")]:
        _REGISTRY.pop(k)


def test_the_engine_that_answered_is_recorded(ref, monkeypatch):
    make("zz.draw")
    monkeypatch.setattr(registry, "resolve", lambda cap: "comfy")
    r = Executor(ref.dir).call("zz.draw")
    assert r.ok
    last = [json.loads(x) for x in (ref.dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert last["module"] == "zz.draw" and last["engines"] == {"image.generate": "comfy"}


def test_no_engine_is_a_plain_needs_input_that_names_the_fallback(ref, monkeypatch):
    make("zz.draw_fb", fallback="fill.placeholder")
    monkeypatch.setattr(registry, "resolve", lambda cap: None)
    r = Executor(ref.dir).call("zz.draw_fb")
    assert r.status == "needs_input" and "image.generate" in r.fix and "fill.placeholder" in r.fix and "Settings" in r.fix


def test_the_real_clip_modules_declare_what_they_need():
    from vt.modules.defs import load
    from vt.modules.registry import get_module

    load()
    assert get_module("gen.video_from_image").engines == ("video.generate",) and get_module("fill.generated_clip").engines == ("video.generate",)
