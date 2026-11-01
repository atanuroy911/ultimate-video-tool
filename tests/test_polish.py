from vt import ai
from vt.ai import polish


def test_suggestions_are_checked_and_decided(ref):
    words = ref.transcript().words
    w0, w1 = words[0], words[1]
    fake = ai.FakeProvider([{"fixes": [
        {"id": w0.id, "text": "Corrected", "why": "name"},
        {"id": w1.id, "text": "two words", "why": "bad: not one word"},
        {"id": "w999", "text": "x"},
        {"id": words[2].id, "text": words[2].text},                       # unchanged
    ]}] * 5)
    res = polish.suggest(ref, provider=fake)
    assert [s["id"] for s in res] == [w0.id] and res[0]["old"] == w0.text and res[0]["status"] == "pending"
    assert polish.load(ref)[0]["text"] == "Corrected"
    out = polish.decide(ref, [w0.id], [])
    assert out["applied"] == [w0.id]
    assert polish.load(ref)[0]["status"] == "accepted"
    import json
    assert json.loads((ref.dir / "edits.json").read_text(encoding="utf-8"))["words"][w0.id]["text"] == "Corrected"
    # a rejected suggestion is not offered again
    fake2 = ai.FakeProvider([{"fixes": [{"id": w0.id, "text": "Other"}]}] * 5)
    assert polish.suggest(ref, provider=fake2)[0]["status"] == "accepted"


def test_no_ai_means_a_clear_error(ref):
    import pytest

    with pytest.raises(ai.AIUnavailable):
        polish.suggest(ref, provider=ai.FakeProvider([ai.AIUnavailable("down")]))
