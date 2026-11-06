# B6: the picture-video (reel) path

Done on 2026-11-06 (plan decision 1).

## What I read
`directors.client_prompt`, `mcp.get_reel_plan` / `check_reel_plan`, `modules/defs/plan.py` (`plan.edit`, `plan.approve`, `plan.decline`), `direction/plan_doc.py` (`apply_edit`, `checks`) and the pipeline's `_reel_plan_for_making`. The reel plan is the director's own document: it edits it one typed operation at a time (each a logged call with a reason), the picture checks only report, and after approval the pipeline makes exactly what the plan says. **No code changes a picture, a place or a prompt behind a director's back**, so there was nothing to remove.

## What was silent, and is not any more
- A director could approve a plan while `picture.place` / `picture.drawable` checks were still open, and nothing said so. Now `plan.approve` by a director with open checks writes a warning to Details, Problems ("Claude approved the plan with 5 picture check(s) still open: ...", with what to do), adds the count to its own log line, and returns `open_checks` and `issues`. The person pressing Start is not second-guessed: they see the plan and its checks and decide.
- `check_reel_plan` says in its description that it changes nothing, and `PD.picture_shots` / `PD.open_picture_issues` (new, used by `_reel_plan_payload` and by the approval) are plain reads.

## Checks
`tests/test_reel_authority.py`, 7 checks: the checks only report (the plan file is the same bytes and was not even written again), an edit changes exactly the moment it names, an edit that cannot be done is refused in a sentence and changes nothing, a director's approval with checks open is written down, a plan whose checks were all fixed leaves nothing to say, the person's Start is not second-guessed, the director's prompt sends it to the checks and the approval. Mutation checks, 6 of 6 caught (one first missed: a read that wrote the same bytes; the test now also compares the file's time). The neighbouring `test_plan.py`, `test_reel.py` and `test_reel_routes.py` pass (52 with the new ones).
