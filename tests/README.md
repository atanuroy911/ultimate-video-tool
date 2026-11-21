# Tests

```sh
uv run --project server pytest -m "not slow"     # the fast suite (CI runs this on every push)
uv run --project server pytest -m slow           # real frames in Chrome, real models
```

Markers: `slow` (real renders or models), `gpu` (needs a graphics card), `models` (downloads or needs a model), `browser` (headless Chrome). See `docs/dev/slow-tests.md` for what each slow test needs.

## Test what the code does, not the words of a prompt

Assert on the parsed result, the chosen scene type, the file written or the request sent, not on whether a sentence appears in a prompt. A prompt test is allowed only for a safety line that must never disappear, and then the test names that line in a constant. About 85 older files still check prompt wording; when you change a code path, convert the tests you touch.

## Servers in tests

Use `TestClient(app, client=(address, port))` to ask as a given computer. A private address needs the server's key unless the test turns on `serve.STATE["trust_network"]`; this computer never does (see `tests/test_server_webpage_guard.py`).
