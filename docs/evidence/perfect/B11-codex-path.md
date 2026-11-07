# B11: the Codex path

Done on 2026-11-06. **Codex is not installed on this PC**, so these checks use a stand-in for the helper (as `client/desktop/test-director-runner.js` already does for the Codex program itself). The Codex program has never been run against this server (BREAKING.md item 16).

## Found and fixed
**Codex was asked for a Claude model.** The server sent the setting `director_model` ("sonnet" or "opus") with every task for Codex too, and `codex-runner.js` turns a model into `-m sonnet`, which Codex does not know: every Codex task would have failed. The setting names a Claude model, so `directors.task_model` is now "" for Codex (it uses the model it is set up with), the helper starts it with no `-m`, and the conversation record shows no Claude model for it.

## Confirmed
- **The same brief:** the planning task sent to Codex is word for word the one sent to Claude (`client_scene_prompt`), naming `preview_frames`, `frame_facts`, `update_scene`, `submit_script` and `craft.check`.
- **The same tools and server:** Codex reaches the same MCP server (`/mcp`), with `frame_facts`, `preview_frames`, `update_scene`, `submit_script`, `submit_story`, the task tools and the reel checks.
- **Questions carry the frame and the facts:** the director's last look sends Codex the frame as a picture (`-i` files in the helper) and the exact measurements in the prompt; what it leaves standing is listed for the person (B2).

## Checks
`tests/test_codex_path.py` (4 checks) and one more line in `client/desktop/test-director-runner.js` (no model, no `-m`, for both Codex commands). Mutation checks: see below.

Mutation checks, 10 of 10 caught across B8, B10 and B11 (settings route, free text, CLI, Codex model twice, limit wording, failure memory, half-made plan, hand-over, asking a failed director again).
