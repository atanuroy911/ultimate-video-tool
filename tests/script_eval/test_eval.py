"""Scores the rule director on the evaluation transcripts (always) and the real model's scripts (only with VT_EVAL_MODEL=1 and a reachable Ollama).

    VT_EVAL_MODEL=1 pytest tests/script_eval -s      # prints a table; fails if the AI does not beat the rules on enough transcripts
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from transcripts import SETS  # noqa: E402

from vt import ai  # noqa: E402
from vt.planner import plan_rules  # noqa: E402
from vt.script import examples as EX  # noqa: E402
from vt.script.planner import ai_script  # noqa: E402
from vt.script.rules_stick import rules_script  # noqa: E402
from vt.script.score import METRICS, compare, score  # noqa: E402
from vt.script import validate_script  # noqa: E402


@pytest.mark.parametrize("name", list(SETS))
def test_rule_director_scores_are_sane(name):
    tr, beats = EX.make(SETS[name])
    sf = plan_rules(tr, beats, "paper", language="bn" if name.startswith("bn") else "en")
    s = rules_script(tr, beats, sf, kind="stick")
    assert validate_script(s.model_dump(by_alias=True), tr, beats) == []
    sc = score(s, tr, beats)
    assert sc["valid"] == 1.0 and sc["coverage"] == 1.0
    assert 0 <= sc["variety"] <= 1 and 0 <= sc["fit"] <= 1


@pytest.mark.skipif(os.environ.get("VT_EVAL_MODEL") != "1", reason="set VT_EVAL_MODEL=1 to run the real model")
def test_real_model_beats_rules(monkeypatch):
    from vt import llm

    monkeypatch.setattr(llm, "settings", lambda: {"llm_mode": "auto", "ollama_url": os.environ.get("VT_OLLAMA", "http://192.168.123.47:11434"),
                                                  "ollama_model": os.environ.get("VT_OLLAMA_MODEL", ""), "llm_auto_download": False})
    if not llm.reachable():
        pytest.skip("no Ollama server reachable")
    wins = 0
    for name, texts in SETS.items():
        tr, beats = EX.make(texts)
        lang = "bn" if name.startswith("bn") else "en"
        sf = plan_rules(tr, beats, "paper", language=lang)
        r = score(rules_script(tr, beats, sf, kind="stick"), tr, beats)
        try:
            a = score(ai_script(tr, beats, kind="stick", language=lang, draft=sf), tr, beats)
        except ai.AIUnavailable as e:
            print(f"{name:20s} AI failed: {str(e)[:200]}".encode("ascii", "replace").decode())
            continue
        cmp = compare(a, r)
        wins += cmp["wins"]
        print(f"{name:20s} " + " ".join(f"{m}:{a[m]:.2f}/{r[m]:.2f}" for m in METRICS) + f"  wins={cmp['wins']}")
    assert wins >= len(SETS) * 0.6
