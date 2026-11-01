from vt.stages import asr


def test_bangla_model_is_only_used_for_bangla():
    assert asr.model_for_language("bn-medium", "bn") == "bn-medium"
    assert asr.model_for_language("bn-medium", "en") in ("medium", "large-v3")   # multilingual fallback
    assert asr.model_for_language("large-v3", "en") == "large-v3"
    assert asr.model_for_language("small", "bn") == "small"                     # an explicit choice is respected


def test_bangla_model_decodes_without_timestamp_tokens():
    """The fine-tune was trained without them; enabling them clips the first word and invites hallucinated tails."""
    assert asr.MODEL_SPECS["bn-medium"]["timestamp_tokens"] is False
    assert all(spec.get("timestamp_tokens", True) for k, spec in asr.MODEL_SPECS.items() if k != "bn-medium")
