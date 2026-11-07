# B10: "Claude ran out of usage" is said, and the video goes on with the next director

Done on 2026-11-06. On 2026-11-05 a Claude run stopped after 20 s on the five-hour limit, exited 0 with `is_error: true` in its final message, and the video carried on as if it had been directed.

## What was already true (M3, checked again)
`director-runner.js` `run()` reads the final `result` message like `ask` does and reports `ok: false, error_kind: "limit"` (also `login`); `client/desktop/test-director-runner.js` feeds both jobs a recorded limit message (`ask` and the planning session, which exits 0). The helper sends `error_kind` and the server's broker passes it on.

## What changed on the server
- `directors.failure_line` says why a computer's Claude or Codex did not finish, in one plain clause: "Claude's usage limit was reached", "Claude is not signed in on that computer", or what it said.
- The pipeline's scene path (`Pipeline.stage_plan`): when the chosen computer's director does not finish, **the next director in the person's order takes the video** (the Local AI, or the rule director if nothing else is there; the same rule the reel path already had), and the video carries **one line** (in Details, the director record and the notice): "Claude's usage limit was reached, so the rule director directed this video." (or "...so Claude on Zulu directed this video."). Before, the rules' draft was used with the helper's raw error text ("5-hour limit reached ∙ resets 3am").
- **Nothing half-made is left:** when it fails, the rules' draft is saved over whatever plan the director had begun to submit (it may have saved a plan marked as its own), so a plan marked Claude never comes from a director that did not finish.

## Checks
`tests/test_usage_limit.py`, 8 checks: a limit hands the video on with exactly that line; a second computer takes it with its own name in the line; a limit, a missing sign-in and any other failure each in plain words; a plan the director had half made is taken back; a director that did finish leaves no failure behind; the wording of `failure_line`. Mutation checks: see the end of this file.

Mutation checks, 10 of 10 caught across B8, B10 and B11 (settings route, free text, CLI, Codex model twice, limit wording, failure memory, half-made plan, hand-over, asking a failed director again).
