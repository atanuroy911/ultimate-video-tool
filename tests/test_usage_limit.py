"""Plan step B10: a director on the person's computer that cannot finish (its usage limit, its sign-in) hands the video to the next director, with one plain line, and leaves no half-made plan.

On 2026-11-05 a Claude run stopped after 20 s on the five-hour limit. It exited 0, the final message said `is_error`, and the video carried on as if it had been directed. The helper now reports
`error_kind: "limit"` (client/desktop/test-director-runner.js feeds both jobs a recorded limit message); these tests are the server's half: what the pipeline does with it."""
from __future__ import annotations

import pytest

from test_one_director import Laptop, _choose, _no_computer_left_connected, _no_plan, _watch_the_other_minds   # noqa: F401  (the autouse fixture comes along)


class Failing(Laptop):
    """A computer whose Claude answers the planning task with a failure, the way helper.js reports one (error and error_kind)."""

    def __init__(self, directors, kind="limit", error="5-hour limit reached ∙ resets 3am", half_done=None, **kw):
        self.kind, self.error, self.half_done = kind, error, half_done
        super().__init__(directors, **kw)

    def send(self, message):
        if message["type"] != "direct":
            return super().send(message)
        self.sent.append(message)
        if self.half_done:
            self.half_done()                                                  # it had submitted part of a plan before it stopped
        self.broker.finish(message["request"], ok=False, error=self.error, detail={"error_kind": self.kind}, device_id=self.device)


def _scene_plan(ref, planner):
    ref.save_scenes(ref.scenes().model_copy(update={"planner": planner}))


def test_a_usage_limit_hands_the_video_on_with_one_plain_line(ref, monkeypatch):
    from vt import directors
    from vt.pipeline import Pipeline
    from vt.util import read_json

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, "claude@laptop")
    Failing(directors)
    Pipeline(ref).stage_plan(force=True)
    line = "Claude's usage limit was reached, so the rule director directed this video."
    assert read_json(ref.dir / "ai_notice.json")["message"] == line
    meta = ref.meta().director
    assert meta["who"] == "rules" and meta["fallback_reason"] == line and meta["requested"] == "claude@laptop"
    assert ref.scenes() is not None and ref.scenes().planner == "rules", "a plan the rules wrote is never credited to Claude"


def test_the_next_computer_in_the_order_takes_the_video(ref, monkeypatch):
    from vt import directors
    from vt.pipeline import Pipeline
    from vt.util import read_json

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, "best")
    Failing(directors, device="laptop", name="Alpha")                    # the computers are offered in the order of their names
    Laptop(directors, device="desk", name="Zulu", plan=lambda m: _scene_plan(ref, "claude"))
    pl = Pipeline(ref)
    pl.stage_plan(force=True)
    assert ref.scenes().planner == "claude" and ref.meta().director["who"] == "claude@desk"
    line = read_json(ref.dir / "ai_notice.json")["message"]
    assert line == "Claude's usage limit was reached, so Claude on Zulu directed this video." and ref.meta().director["fallback_reason"] == line


@pytest.mark.parametrize("kind,error,says", [
    ("limit", "Claude AI usage limit reached|1730000000", "Claude's usage limit was reached"),
    ("login", "Claude is not signed in on this computer.", "Claude is not signed in on that computer"),
    ("other", "Claude Code gave no JSON answer (exit 1): boom", "Claude on Laptop did not finish (Claude Code gave no JSON answer (exit 1): boom)"),
])
def test_each_kind_of_failure_is_said_in_plain_words(ref, monkeypatch, kind, error, says):
    from vt import directors
    from vt.pipeline import Pipeline
    from vt.util import read_json

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, "claude@laptop")
    Failing(directors, kind=kind, error=error)
    Pipeline(ref).stage_plan(force=True)
    assert read_json(ref.dir / "ai_notice.json")["message"] == f"{says}, so the rule director directed this video."


def test_nothing_the_director_half_made_is_left(ref, monkeypatch):
    from vt import directors
    from vt.pipeline import Pipeline

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, "claude@laptop")
    first = ref.scenes().scenes[0].id if ref.scenes() else "s1"
    Failing(directors, half_done=lambda: _scene_plan(ref, "claude"))             # it saved a plan marked as its own, then ran out
    Pipeline(ref).stage_plan(force=True)
    sf = ref.scenes()
    assert sf.planner == "rules", f"the half-made plan was taken back (it was {sf.planner})"
    assert ref.meta().director["who"] == "rules"


def test_a_director_that_did_finish_leaves_no_failure_behind(ref, monkeypatch):
    from vt import directors
    from vt.pipeline import Pipeline
    from vt.util import read_json

    _no_plan(ref)
    _watch_the_other_minds(monkeypatch)
    _choose(ref, "claude@laptop")
    Laptop(directors, plan=lambda m: _scene_plan(ref, "claude"))
    pl = Pipeline(ref)
    pl.stage_plan(force=True)
    assert pl._failed == {} and ref.scenes().planner == "claude" and ref.meta().director["who"] == "claude@laptop"
    notice = read_json(ref.dir / "ai_notice.json", None)
    assert not notice or "usage limit" not in notice.get("message", "")


def test_the_words_a_director_gets_back_name_the_limit():
    from vt import directors

    assert directors.failure_line("claude@pc", {"error_kind": "limit"}, "Claude on PC") == "Claude's usage limit was reached"
    assert directors.failure_line("codex@pc", {"error_kind": "limit"}, "Codex on PC") == "Codex's usage limit was reached"
    assert directors.failure_line("codex@pc", {"error_kind": "login"}, "Codex on PC") == "Codex is not signed in on that computer"
    assert directors.failure_line("claude@pc", {"reason": "It did not answer in time."}, "Claude on PC") == "Claude on PC did not finish (It did not answer in time)"
    assert directors.failure_line("claude@pc", {}, "Claude on PC").endswith("(it did not submit a valid plan)")
