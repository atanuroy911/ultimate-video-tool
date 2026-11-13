# Contributing to Ultimate Video Tool

Thank you for helping. Bug reports, test recordings, looks, scene types, translations of the *video* language, docs and code are all welcome.

## Before you start

- **Small fixes** (typos, clear bugs, docs) can go straight to a pull request.
- **Bigger changes** (a new scene type, a new director, a new engine, a UI rework): open an issue or a discussion first, so we can agree on the shape before you spend time on it.
- Read [docs/HANDOFF.md](docs/HANDOFF.md) for how the repository is organised, and [docs/GLOSSARY.md](docs/GLOSSARY.md) for the words the app uses.

## Set up a development copy

```powershell
./scripts/dev-install.ps1 -Role both      # Windows
```

```sh
bash scripts/dev-install.sh --role both   # Linux
```

The scripts put Node, Python (through uv) and every dependency in a private folder and never touch your system Python. Details are in [docs/DEVELOPMENT-INSTALL.md](docs/DEVELOPMENT-INSTALL.md).

## Run the checks

These are the same checks CI runs on every pull request:

```sh
uv sync --project server --frozen --extra dev --extra cpu --python 3.11
uv run --project server pytest -m "not slow"        # Python tests (slow ones need a GPU)
uv run --project server python scripts/check_docs.py # docs: links, paths and measured facts

cd client/studio
npm ci && npm run build && npm run test:timeline     # editor types, build and timeline tests
```

Tests marked `slow` need a GPU machine and real models. If your change touches speech, rendering or the director, say in the pull request what you ran and on what hardware.

## How we build things

These rules keep the product coherent. Pull requests that break them will be asked to change.

1. **The UI wraps everything.** People using the app never have to run a command. Every capability is written once as a function in `server/vt/`, and is reached three ways: an `/api` route the editor uses, a `vt` command, and (where useful) an MCP tool.
2. **The AI directs.** When a video looks wrong, teach the director (a better prompt, a house rule in `vt/house_rules.py`, or a new ability) rather than adding code that overrides its plan. Built-in rules are only the fallback when no AI answers, and the app says when they were used.
3. **One director per video.** Never mix models within one video. Every prompt and answer must stay visible in *Details → AI conversations*.
4. **Plain words.** Labels, errors and docs say what happens in everyday language. No jargon in the UI.
5. **Client and server stay separate.** The client never imports server code. The server never serves the editor.
6. **Windows and Linux.** Anything you add must work on both.
7. **No secrets in the repository.** API keys live in the OS keychain or the server's data folder.

## Pull requests

- Keep each pull request to one change, and describe what a person will notice.
- Add or update tests. For UI changes, add screenshots in light and dark themes, at desktop and phone widths.
- Update the docs your change affects (`docs/STATUS.md` for features), and run `scripts/check_docs.py`.
- Ported code keeps its original notice and source path in a header comment (see `client/studio/src/occ/NOTICE.md`).

## Licence of contributions

Ultimate Video Tool is licensed under the [GNU AGPL-3.0-or-later](LICENSE). By submitting a contribution you agree that it is licensed under the same terms (inbound = outbound), and that you have the right to submit it.

Only add media (music, pictures, fonts, models) with a licence that allows redistribution, and record it in [THIRD-PARTY.md](THIRD-PARTY.md). We cannot accept NC (non-commercial), ND (no derivatives) or unknown-licence assets in the repository.
