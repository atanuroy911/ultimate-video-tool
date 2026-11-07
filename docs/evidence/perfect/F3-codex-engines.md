# F3 engine failures — Done by codex

2026-11-06. Fake HTTP/process boundaries only; no real engine, GPU, model, speech or video render.

Local AI, OpenAI-compatible and Claude API errors now explain the recovery step for refused keys/accounts, missing models/addresses, usage limits, unavailable servers, connection failures, timeouts and malformed answers. Requests, headers, raw response bodies and exception class names are not included in these user-facing errors. Direct local chat uses the same translation.

New tests exercise the real provider adapters with fake HTTP responses for all three providers and eight failure types. They also confirm that the actual script service returns a valid rule plan when its AI fails, with the reason retained, and that a down or slow ComfyUI connection returns a recoverable status. The existing AI provider tests also passed.

Final check: from `server`, `.venv` pytest selection `tests/test_engine_failures.py tests/test_ai_providers.py tests/test_modules_engines.py` — **48 passed**, six existing FastAPI lifecycle deprecation warnings. No tests were disabled.

Additional integration checks cover a missing local model without an unapproved download, ComfyUI rejecting a missing model or being unreachable before it changes project/media/scene files, a slow ComfyUI request being stopped by its own id and a subsequent request succeeding, and the actual pipeline planning stage completing with a saved rule plan, a completed plan checkpoint, correct rule-director attribution and a plain timeout notice after its AI fails. The initial pipeline fixture retained a protected manual plan and correctly did not replace it; starting with a fresh temporary plan tests the intended failure path.

These checks prove recoverable processing and valid rule-plan completion with fakes. They do not prove a finished exported video, real engine behavior or real service latency. Real heavy processing remains paused.
