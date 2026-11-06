# B2: code no longer hides, shrinks or drops what an AI placed

Done on 2026-11-06 (plan decision 1). Everything below was measured on the real composition in a headless browser with software drawing (no graphics card); the Quality-check card was checked in the Studio with the server's answer stood in for.

## What changed
| Where | Before | Now |
|---|---|---|
| `compose/composer.py` | nothing marked who planned a scene | a scene of a plan whose `planner` is `llm`, `claude` or `assistant` gets `directed`. A scene the person edited (`start`, an edited element) stays `edited`, whoever planned the rest. |
| `renderer/runtime/vt.js` `guardLayout` | shrank, hid or dropped elements on every scene | **Directed scene:** changes nothing. It records `would-shrink`, `would-drop` or `left` in `window.__guard` (with `directed: true`). **Rules and manual plans:** the guard acts as before, and now it really holds (see the two bugs below). |
| `renderer/runtime/vt-stick.js` `frameProps` | hid a prop the shot cuts | a directed scene keeps the prop and records `would-drop` (step B3 covers its tests). |
| `renderer/scripts/frame-facts.mjs` | measured covering and edges only | also says what the guard would have done: "element 1 (tag) has letters too small to read on a phone", "runs off the frame", "overlaps element 0 by more than a fifth", "no free room beside the person". A finding the geometry already says is not said twice; an element that is not on screen at that moment (another page of the scene) is not reported. |
| `director_review.py` | the facts were thrown away after the rounds | `report["left"]` = what is still wrong in the cut as it now stands (measured again after the last change). Information lines ("Nothing covers any character", "Empty across the frame") are not trouble. |
| `layout_check.py` (new) + `pipeline.stage_compose` | the guard's decisions were only in `window.__guard` | for a plan no AI directed, what the guard did is written to Details, Problems (call log, `layout.guard`, level warn), one entry per scene, once per plan. Off with `VT_LAYOUT_CHECK=0` (tests). |
| `GET /api/projects/{pid}/look-at` + `QualityCheck.tsx` | nothing | the Quality check lists "Left to look at" (AI plans), "The director looked at every scene, and nothing is left to fix", or "Changed by the layout guard" (rule plans). A cut nobody could measure claims nothing; a plan changed since is said so; an older server shows the card as before. |

## What I found while testing, and fixed (these were bugs in the old guard)
1. **A dropped element came back.** The guard set `display: none` inline, but `flowStages` writes `display` again when each element arrives in the timeline, so every late element the guard "dropped" appeared anyway. Now a dropped element gets the class `vt-gone` (`display: none !important`).
2. **A shrink was lost on the first frame.** The guard appended `scale(k)` to `transform`, and GSAP rewrites `transform` on every render (measured: 1241 px, 621 px after the guard, 1241 px again after the timeline ran). It now uses the CSS `scale` property (measured: 621 px stays).
3. **Groups one above the other overflowed together.** `shrinkStages` compared each group's height with the stage separately, so a tall frame with two groups (split layout) with four cards ran off the top. Groups stacked in a column now share the stage's height.
4. **Nothing fitted sideways.** A long unbreakable word, or a grid column that grows to hold its widest item, ran off the frame (and a rule plan then shrank or dropped something). `fitGroups` (first step of `guardLayout`, directed or not, layout's job) scales the group together about the middle of what it holds, never below 45 %, and moves it back inside the stage only when it has no neighbours.
5. **Tried and rejected:** fitting width with the stage's `--s` scale. Fit-text elements do not follow `--s` (a big number went 894 px to 859 px when `--s` fell to 0.47), and the next `runFit` then made it 1556 px wide: worse. Traced with a copy of `vt.js` that logged each iteration.

## Checks
- `tests/test_director_authority.py`: 50 checks. For each of four crowds (an element cut off and shrunk, optional elements cut off and dropped, letters too small, one element on top of another) and each of the three AI directors (`llm`, `claude`, `assistant`) and the rules: the rules' plan keeps the guard (what it drops is never on the page, not even when its turn comes in the timeline); an AI's plan keeps every element, shown, at its size, and the guard records the same findings as `would-...`; the facts say each of them. Two crowds that used to run off the frame (a long word in a wide grid; four cards one above the other) now fit with nothing left for the guard. Plus the composer flag for all five planners and an edited scene, the Details, Problems entry (wording, once per plan, again for a changed plan, never for an AI plan, never stops a video), the pipeline hook, `left` (information is not trouble, measured again after the last change, a cut nobody measured is not called clean) and the API.
- Mutation checks (break the fix, a test must fail): see the end of this file.
- The reference video in 9:16, 16:9 and 1:1: 80 element boxes each at 14 times, old runtime against new, identical.
- Two crowds drawn old beside new in software and looked at: the four cards now fit (before, the first was cut by the top edge); a long word in a grid now shows whole (before, both words were cut at the frame edges).
- `client/studio/e2e/look_at.mjs`: 21 checks (the list, the clean line, a changed plan, a cut nobody measured, rules' changes, an older server, phone width in light and dark).

## What is left (parked in BREAKING.md)
- A word that needs less than 45 % to fit still runs a little past the frame; the guard (rules) or the facts (an AI plan) deal with it.
- A grid column holding a row of four numbers still crushes it (the numbers overlap); the facts say so.
- Several groups side by side whose texts overflow their own slots still overlap each other; the facts say so ("element 1 covers 80 % of element 0").

## Mutation checks (each break must make a test fail; the file is put back afterwards)
Page side, 9 of 9 caught: the guard ignores the `directed` flag; the composer never marks a scene directed; the facts say nothing of the guard; a drop by inline `display` (the old way); a shrink appended to `transform` (the old way); a director's tag is still hidden; a director's cut-off element is still shrunk; layout never fits a group across; stacked groups do not share the stage's height.
Report side, 8 of 8 caught: `left` is never filled in; information lines count as trouble; the last round's change is not measured again; a cut nobody measured is called clean; an AI's plan is read for the guard too; the same plan is written again and again; measured things are called changes; the pipeline never reads the guard.

## Neighbouring tests after the change
`test_director_authority.py`, `test_composer.py`, `test_people.py`, `test_one_director.py`, `test_api.py`, `test_modules_calls.py`, `test_hyperframes_check.py`, `test_free_editor_timing.py`, `test_scene_direction.py`: 148 passed (2026-11-06).
