"""The director's first three tools must expose complete, valid contracts."""
import numpy as np
import pytest
import soundfile as sf

from vt.modules.defs import load
from vt.modules.executor import Executor
from vt.modules.registry import get_module, lint_registry, list_modules
from vt.modules.workspace import KNOWN_ARTIFACTS


def test_builtin_contracts_are_described_and_examples_render():
    load()
    assert not lint_registry(known_artifacts=KNOWN_ARTIFACTS)
    assert {spec.id for spec in list_modules()} >= {
        "project.inspect_source", "audio.find_retakes", "audio.prosody",
    }
    assert get_module("audio.find_retakes").effects == "writes_artifact"


@pytest.mark.parametrize("module_id", ["project.inspect_source", "audio.find_retakes", "audio.prosody"])
def test_spike_examples_execute_through_contract(tmp_path, module_id):
    load()
    sf.write(str(tmp_path / "input.wav"), np.zeros(24000, dtype="float32"), 24000)
    (tmp_path / "transcript.raw.json").write_text('{"words": []}', encoding="utf-8")
    spec = get_module(module_id)
    result = Executor(tmp_path).call(module_id, spec.examples[0].inputs)
    assert result.ok, result.fix
    assert spec.outputs.model_validate(result.output)
    assert {ref["type"] for ref in result.artifacts} == set(spec.produces)
