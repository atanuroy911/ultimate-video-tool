# H7 - Versions and packaging

`tests/test_packaging.py`: 8 passed. `scripts/set_version.py 1.4.2` changed the number in `server/pyproject.toml`, `server/uv.lock` (its own entry), `client/desktop/package.json` and `server/desktop/package.json`, all four read 1.4.2 afterwards; `set_version.py 1.0.0` put all four back (`--show` says 1.0.0, nothing else differs). `client/studio/package.json` carries 0.1.0 on purpose: it is the page's build, not a release.
