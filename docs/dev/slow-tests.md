# The slow tests (`pytest -m slow`): what each needs

Measured 2026-11-20 on the Windows laptop (CPU build of torch, RTX 4050 present, Chrome installed): **60 passed, 8 skipped, 0 failed, 9 min 2 s** (68 tests). Skips are tests whose model or sample is not on this laptop; they pass or skip, never fail, when it is absent.

Markers (registered in `tests/conftest.py`): `browser` (renders in headless Chrome through HyperFrames), `models` (a speech, voice or picture model), `network` (the internet), `assistant` (Claude Code or Codex signed in), `gpu` (an NVIDIA card and the CUDA build of torch). None of the 68 slow tests needs `gpu`, so `pytest -m "slow and not gpu"` runs all of them. The three `gpu` tests are in `tests/test_gpu.py` (fast suite); they skip on a CPU build of torch.

| File | Tests | Needs | Time here | Result |
|---|---:|---|---:|---|
| `test_evaluation.py` | 23 | browser | 134 s | passed |
| `test_stick_render.py` | 2 | browser | 100 s | passed |
| `test_backdrop_render.py` | 9 | browser | 87 s | passed |
| `test_phase2_render.py` | 9 | browser | 57 s | passed |
| `test_render_golden.py` | 6 | browser | 50 s | passed |
| `test_ingest_network.py` | 3 | network | 35 s | passed |
| `test_tts.py` | 1 | models, network (online voices) | 26 s | passed |
| `test_stick.py` | 3 | browser | 22 s | passed |
| `test_api.py::test_jobs_run_and_report` | 1 | speech model on CPU | 9 s | passed |
| `test_vision.py` | 1 | browser | 8 s | passed |
| `test_handback.py` | 1 | browser | 5 s | passed |
| `test_cutout.py` | 1 | models (background removal model, downloaded on first use) | 5 s | passed |
| `test_modules_equivalence.py` | 2 | models and sample audio (`samples/audio/`) | 1 s | skipped: samples missing |
| `test_pipeline_real.py` | 3 | models (the Bangla speech model, `vt models pull bn-medium`) | 0 s | skipped: model not downloaded |
| `test_clone_onnx.py` | 1 | models (Chatterbox Turbo bundle) | 0 s | skipped: bundle not downloaded |
| `test_source_inspect.py` | 1 | a podcast sample | 0 s | skipped: sample missing |
| `test_claude_cli.py` | 1 | assistant (Claude Code signed in) | 0 s | skipped here (the check does not find the signed-in program from the test environment) |

Selections: `slow and browser` = 54, `slow and models` = 9, `slow and network` = 4, `slow and assistant` = 1.

CPU-feasible on a GitHub runner (nightly, W3.3): all `browser` tests (HyperFrames downloads its own Chrome), `network`, and the CPU speech model of `test_api`. The `models` tests skip themselves when the model is absent; the nightly job can cache the models it wants.
