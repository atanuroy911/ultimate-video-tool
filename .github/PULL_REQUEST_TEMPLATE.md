## What changes for the person using it

<!-- One or two sentences in plain words. Screenshots (light and dark) for UI changes. -->

## How it was checked

- [ ] `uv run --project server pytest -m "not slow"`
- [ ] `npm --prefix client/studio run build` and `npm --prefix client/studio run test:timeline`
- [ ] `uv run --project server python scripts/check_docs.py`
- [ ] Real video made (say which director, style and hardware), if speech, direction or rendering changed

## Notes

- [ ] Every new capability is reachable from the UI, and also as a `vt` command or MCP tool where useful
- [ ] Works on Windows and Linux
- [ ] New media or models have a redistributable licence, recorded in THIRD-PARTY.md
