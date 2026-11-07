# C3 and C4 cartoon vocabulary — Done by codex

2026-11-06. Implemented and checked locally with pure Python contracts and the production SVG runtime in software Chrome (`--disable-gpu`). The browser context was offline. No model, speech recognition, GPU run, video render, owner-server call or commit ran.

## Implemented

- `idle` has a relaxed weight/head sway. `run` uses a forward lean, articulated elbows/knees, faster opposing leg/arm cycles and bounce. `laugh` has shaking shoulders, a rocking head, open smiling mouth and closed laughing eyes. `count` raises a hand and reveals the requested fingers. `confused` scratches the head with asymmetric brows, a puzzled mouth and a question mark. `ride` draws a bicycle with wheels, frame, handlebars, saddle and crank, and animates pedaling. These are distinct rigs/animation branches, rather than aliases for standing or walking.
- Added the six poses and the `laugh`/`confused` expressions to the schema. Expressions also work independently on a standing person.
- `count` supports one through five fingers. `CastMember.count` defaults to three; `CartoonCue.count` can override it or inherit the character's count. The Story kit forwards a script director's `Action.count`, and the browser test feeds the actual production compile/Story-kit output for `count=5` into the SVG runtime and verifies five visible fingers.
- Added `old_woman`: grey bun, glasses, earrings, age lines and skirt. `elder` retains the older man's bald/glasses look. The Story kit distinguishes an elder woman from an elder man when the supplied cast style describes long/bun hair, and keeps supplied shirt colours.
- Added `CastMember.hair` and `clothes` as empty or `#RRGGBB`. Empty preserves the automatic palette from `who` plus `name`; explicit values are reused directly. Appearance does not depend on scene index, pose or cast order.
- Director prompts list the new schema values and explain colours, the included bicycle and count. The editor agent supplied matching pose pictures/titles and colour controls with an Automatic reset.
- Pose changes reset bicycle visibility, finger visibility, limb bends, hand rotation, face expression and riding arm offsets; forward and backward timeline seeks are checked.

## Checks

Regression-first: all **15 initial vocabulary/contract tests failed** against the old schema/mapping. The additional requested-count regression then failed before adding the count fields/forwarding.

Final check after the implementation edits, working directory `server`:

```text
..\.venv\Scripts\python.exe -m pytest -q -c NUL --rootdir=.. ..\tests\test_cartoon_poses.py ..\tests\test_story_kit.py ..\tests\test_script.py::test_json_schema_is_exportable ..\tests\test_script.py::test_prompt_contains_all_parts ..\tests\test_script.py::test_good_script_validates_and_compiles
27 passed, 6 warnings in 6.55s
```

The six warnings are existing FastAPI `on_event` deprecations.

Final software-browser check, working directory `client/studio`:

```text
node e2e/cartoon_vocabulary.mjs
PASS: 150 who/pose combinations, six distinct animated poses, bicycle, counting fingers, laughing face, automatic/explicit identity, forward/backward cue resets.
```

The browser fixture reads the current `CharacterId`/`Pose` vocabulary and a real compiled director-count cue through `scripts/lab/cartoon_vocabulary_fixture.py`; it does not maintain a second list of accepted values. Its recorded results are `client/studio/e2e/out/cartoon-vocabulary/checks.json`.
Its Python launcher uses the platform's repository `.venv` path, or `VT_PYTHON` when supplied. The final launcher-only portability edit was syntax-checked with `node --check e2e/cartoon_vocabulary.mjs`; the Windows executable path used by the full run is unchanged.

## Viewed results

All 10 `who` values in all 15 poses were produced and visually inspected in these contact sheets:

- `client/studio/e2e/out/cartoon-vocabulary/all-people-poses-1.png`: stand, point, think, wave, celebrate.
- `client/studio/e2e/out/cartoon-vocabulary/all-people-poses-2.png`: sad, shrug, walk, sit, idle.
- `client/studio/e2e/out/cartoon-vocabulary/all-people-poses-3.png`: run, laugh, count, confused, ride.

Detail sheets were also inspected:

- `new-poses-detail.png`: the six new poses at a larger size.
- `new-expressions.png`: laughing and confused faces independently of the standing body, on a woman, elder woman and robot.
- `count-one-to-five.png`: requested counts one through five and the actual script-director count-five cue. The correct number of fingers is visible in each.
- `identity-and-colours.png`: the same named elder woman in two scenes with the automatic palette, then the same named person with explicit hair/clothes in two poses; two adults with distinct chosen colours. Exact pre-animation SVG identity matches across scenes in both automatic and explicit cases.

All detail sheets are under `client/studio/e2e/out/cartoon-vocabulary/`. The first contact-sheet pass enlarged actors enough to crop some existing pointing hands; fixture sizing was corrected and all three final sheets were viewed with the hands inside their tiles.

Limits: these checks prove the shared SVG drawings, deterministic paused-timeline animation/seek behavior, contract compatibility and character consistency in a software-browser fixture. They do not prove a fresh director makes good scene choices or that a full video export looks good. Real video work remains paused under the owner's instruction.
