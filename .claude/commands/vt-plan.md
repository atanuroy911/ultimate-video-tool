---
description: Plan the scenes for every video waiting for Claude in the Video Tool Studio
---

Plan all pending Video Tool requests.

1. Call `list_pending_requests`. If it is empty, say so and stop.
2. For each request, call `get_planning_task` (project + request id) and read its `instructions` carefully. The task contains the
   timed sentences (beats with word ids), the component catalogue with field limits and examples, and a draft plan from the rules planner.
3. Write the scenes and call `submit_scenes`. If it returns `errors`, fix exactly those problems and submit again until `ok` is true.
   - For a whole-video request, submit one scene list that covers every beat once, in order.
   - For a single-scene request, submit one scene object, or as many different alternatives as `alternatives` asks for.
4. When a whole video is planned, call `get_preview_frame` for two or three moments (for example the busiest scene) to check that text fits
   and nothing overlaps. If something is wrong, use `update_scene` to adjust it.
5. Finish with a short summary per video: how many scenes, which visuals you chose and why, and anything the user should double check
   (for example numbers you were unsure about).

Do not invent facts: put only numbers and terms the speaker actually said into elements.
