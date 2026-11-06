# B5: Cartoon 2 (story videos) does not change a director's story behind its back

Done on 2026-11-06 (plan decision 1).

## What changed
- `story/engine_validate.py` `validate(..., notes=None)`: every change it makes to a story is described as a note `{scene, says, meaning}` (scene numbers count from 1). **Drops or replaces what the director wrote (meaning):** an element type it cannot draw, a background it does not have (now plain), a speaker who is not in the characters, a sound it does not know (this one used to disappear with no warning at all). **Only moved a little (small):** a first scene that did not start at 0, a gap under 0.6 s closed, a last scene that ended before the video, an element's time outside its scene.
- `story/service.py` `submit_story`: a director that can answer (Claude or Codex over MCP, `planner` anything but `manual`) gets what it would have had to drop or replace as **errors**, and nothing is applied until it submits again; the small things come back in `repairs`. The person's own edit (`manual`) is applied as repaired. **Every warning comes back** (up to 60, then a count `warnings_not_listed`), where only the first eight did. What was repaired is written to Details, Problems (`script/repairs.record`, now saying "story" or "Video Script").
- The local AI's story (`plan_story`, after `designer.refine`) records its repairs the same way.
- `directors.client_story_prompt` and `get_story_task`'s `how_to` tell the director: "Nothing is changed behind your back: whatever the app would have had to drop or replace ... comes back as an error; fix every error and submit again, and treat every warning as something to fix too."

## Checks
`tests/test_story_repairs.py`, 15 checks: one per kind of change (8: four of meaning, four small), a story that needs nothing has no notes, a director told and nothing applied (an unknown element type, then an unknown background), small things in `repairs` with the story applied, the person's own edit applied with its Details, Problems entry, 20 and then 80 warnings all or counted, the MCP tool and both prompts, the local AI's story with its entry (and none for the rule director's). Mutation checks, 10 of 10 caught. The existing story tests pass (`test_story_engine.py`, `test_story_kit.py`, `test_story.py`: 39 with the new ones, 2026-11-06).
