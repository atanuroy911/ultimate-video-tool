# B8: the person chooses which Claude directs (decision 3)

Done on 2026-11-06.

## What changed
- **Settings, Directors and assistants** has a labelled choice, "Which Claude directs": **Sonnet: faster** (the default) and **Opus: slower, the most careful**. It is saved on the server (`PUT /api/settings`, `director_model`), shown again after a reload, and read by the very next task, with no restart. Nothing but a model name is saved (`directors.model_name`): `--dangerously-skip-permissions`, `opus; rm -rf /` and the like become the default. A full name such as `claude-opus-5-5` is still accepted through the API and the command line.
- **The `vt` command line:** `vt directors --model opus` (or `sonnet`) saves the same setting and says "Claude will direct with opus from the next video."; `vt directors` alone still lists who can direct.
- The server already sent the setting with every `direct` and `ask` task (M3, M4); the helper starts Claude with `--model`.

## The check: the model of the real run
"Earlier 'Sonnet' results came only from a test script passing the flag, so this must be read from the real run." On this PC, with its own signed-in Claude Code 2.1.314, through the helper's own runner (`client/desktop/director-runner.js`):

| choice | planning session (`run`), model in the `init` line | one question (`ask`), models used |
|---|---|---|
| Sonnet | `claude-sonnet-5-5`, built-in tools: none | `claude-sonnet-5-5` (and `claude-haiku-5-5`, which Claude Code uses for its own housekeeping) |
| Opus | `claude-opus-5-5`, built-in tools: none | `claude-opus-5-5` (and `claude-haiku-5-5`) |

(A one-word question each; about 4 s each.) The Settings and CLI choice reaches those runs through the task's `model`: `tests/test_director_model.py` follows it from the page to the message the helper receives.

## Checks
`tests/test_director_model.py`, 8 checks (the default; the page saves each choice; nothing but a model name is saved; every `direct` and `ask` task carries the choice; a change reaches the next task without a restart; the command line chooses, and free text becomes the default); `client/studio/e2e/director_model.mjs`, 16 browser checks (labelled in plain words, the two choices say what they cost, saved and kept after a reload, wide and phone width, light and dark, no sideways scroll); screenshots viewed.

Mutation checks, 10 of 10 caught across B8, B10 and B11 (settings route, free text, CLI, Codex model twice, limit wording, failure memory, half-made plan, hand-over, asking a failed director again).
