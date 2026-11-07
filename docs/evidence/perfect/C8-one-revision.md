# C8 - The director's one revision (gemma)

Three fresh cartoon/stick videos with the local gemma director on the server (9:16, same story as the lab): `2026-11-07-c8-b` (cartoon), `2026-11-07-c8-c` (stick), `2026-11-07-c8-d` (cartoon, made after the fix below). Server uptime read 5:40 at the start of the earlier runs and 15:11 at the end, with no restart.

What is on record for each video: `director_review.json` (Details) holds, per scene, the measured facts the director was given (before), what it changed or why a change was refused, and `left` (after, measured again on the changed cut). `GET /look-at` gives `left` to the Quality check.

| video | before the one revision | what is left (Quality check) |
|---|---|---|
| c8-b | stickers cover 100% of two faces in scenes 2 and 3, small labels, a half-transparent caption | the director's own list said nothing left, but the cut had been rewritten later (see the bug); remeasured: still 100% face cover at 10 s and 17 s |
| c8-c | window and key props cut by the shot, small labels | 3 items: prop cut by the shot in scenes 1, 2 and 3 |
| c8-d | stickers cover 67 to 100% of faces, small labels, caption at 42 to 70% | listed per scene, current with the saved plan |

Pictures match their words in the contact sheets (`dist/lab/c8-b.png`, `c8-c.png`): a piggy bank for "coin", a bicycle, a mother, a shop, a clock at "10 o'clock", keys. No car for "coin" and no rocket for "shop".

Limit found (recorded as the plan asks): when a sticker (here the big "Mother" face) covers 100% of two faces, one gemma revision does not move it. The facts reach gemma first and it answers, but a refusal or no change leaves the cover. The person fixes it with the element controls (E17).

## Bug found and fixed while doing this

After the director's look the pipeline renders, runs the viewer test, and `watch_and_revise` (server/vt/server/app.py) can ask the director to rewrite the plan once more and keep it when the risk drops (c8-d: 60 to 24). The saved plan then no longer matched `director_review.json`, so `/look-at` said `current: false` and the Quality check had nothing true to show. Fix: `director_review.remeasure` measures the kept cut with the page only (nobody is asked, nothing is changed, what the director saw stays) and writes `left` for the saved plan. Tests: `test_a_cut_changed_after_the_look_is_measured_again_so_the_quality_check_is_not_stale` and `test_a_cut_nobody_looked_at_is_not_given_a_record_by_the_remeasure` (mutation checked: stop updating `left` and the first fails).

Also seen: one video (`c8-a`) fell back to the rule director with "Script step skipped: TypeError: 'str' object does not support item assignment". It could not be reproduced from the AI's saved answers (repair, enrich, animalize, toonify, compile and story kit all ran clean on them). The plan stage now writes the traceback to the video's technical log (`pipeline.plan: script step failed`), so the next occurrence names the line. Parked in BREAKING.md.
