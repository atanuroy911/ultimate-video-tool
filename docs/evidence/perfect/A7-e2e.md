# A7: every browser suite, sorted (2026-11-08, Claude)

**How they ran.** On the owner's Windows PC, against a local scratch server (`--gpus none`, `CUDA_VISIBLE_DEVICES=-1`, engines off, a fresh `reference` from `vt demo`), through a new guard (`scripts/lab/e2e_guard.mjs`). The guard refuses with 423 every request that would start heavy work: export, render, speech recognition, a pipeline, a new video, downloads, frame checks, covers and thumbnails. Section 0.1 forbids that work on this PC. `scripts/lab/run_e2e.py` now copies `reference` and the settings file before each suite and puts them back after, so no result depends on the order. Headless Chrome with `--disable-gpu`. Final sweep: **56 of 71 pass here**. The other 15 need the GPU server's scratch (8792) or something only it has; none fails for a reason found in the app.

## Pass here (56)
| Suite | Result |
|---|---|
| catalog_refresh 18, connection 12, contrast 14, credits 12, director_model 16, editor 23, engines 11, gpu_card 37, helper_card 25, house_rules 10, keyboard 16, layers 20, layers_media 11, log 13, look_at 21, new_moved_choices 34, new_tiles 12, plan 28, plan_undo 7, qa_frames 6, quality 10, script 11, scroll 8, server_manager 12, server_page 16, server_pages 21, states 180, timeline2 8, timeline3 13, dashboard 10 | all checks pass |
| cartoon_vocabulary, details_readability, drag_smooth, editor_cleanup, flow, frame_measurements, job_recovery, menus, motion, navigation_dashboard, perf_timeline, redo_choices, result_cleanup, server_restart, settings_audit, settings_clarity, shorts_swipe, transform_controls, walk_new, word_motion | exit 0 (they print PASS lines, not counts) |
| crawl | 116 interactions on 8 pages, 0 problems, **62 s**. The roadmap's "over 10 minutes" is gone: the 1 s action limit and per-page budgets (Codex) bound it. |
| shots, shot_sec, shots_all, shots_extra | screenshot tools, exit 0. `shots` went from 505 s to 61 s (it waited for a quiet network, which the editor's audio never gives). |
| a11y | exits 0 but **skips itself without `AXE=<axe.min.js>`**; E12 ran it with axe (0 serious or critical). |

## Need the GPU server's scratch (15)
| Suite | Why it cannot pass here |
|---|---|
| new_flow, simple, design, journey, edge, export, retention, director | make or export a real video (the guard refuses it). Their screens up to "Make my video" were updated and pass. |
| context, sounds | run a server job (reading the video, listening for sounds). |
| transform | 38 of 43; the 5 left are the guard refusing scene thumbnails (counted as console errors). |
| comfy, comfy_place | need a live ComfyUI and a generated clip. |
| stick | needs a project with a stick-figure plan. |
| connect | must be opened by the server's network address, not 127.0.0.1. |

## Real bugs found and fixed
- **Timeline chips narrower than 44 px were empty** (no icon and no name). The icon is now always drawn. (`Timeline.tsx`; `editor_cleanup`)
- **Typing a value in Position made a laid-out element jump to its own size.** "Stretch across 200%" shrank it from 828 × 359 to 712 × 188. Dragging already kept the size; typing now does the same: the preview shares the measured fit (`transformUi.ts` `setMeasured`, `Preview.tsx`, `VisualControls.tsx`). (`transform`: the picture is twice as wide)
- **The caption look could not be changed after a video was made.** It was removed with the old editor on 2026-11-03. It's back in the editor's Captions tab, with the New page's eight choices and names (`review/CaptionLook.tsx`). The server now validates `options` on `PATCH /api/projects/{id}`; before, a wrong value was stored as-is (`tests/test_project_options.py`, which fails on the old code). (`quality`)
- **A picture video's plan could not be opened from the editor** ("Change the look, pictures or pace"). It was removed with the old editor; it's restored in the AI panel. (`plan`)
- **Settings crashed** when the house-rules answer was not a list (`rules.map is not a function`). It's now tolerant. (`settings_clarity`)
- B8's wording had drifted. "Which Claude directs", "Opus: slower, the most careful" are restored. (`director_model`)
- The preview's play controls had no name; they're now a "Playback" toolbar. "The editor still notes" became "Still to look at" (E1). The bin's picture "Add to timeline" got the same accessible name as the sound one.
- The `plan` suite left `reference` as a waiting picture video and changed two settings, so later suites failed. It now restores both, and the runner resets them per suite. My first runner version kept its copy inside `projects/`, where the server listed it as a second video (crawl's duplicate-key warning, dashboard's extra tiles). It's now kept outside.

## Out-of-date suites updated (the app changed, the suites had not)
keyboard and new_tiles (15 tiles), simple (step 2 is "Where will it be posted?"), script, scroll (the editor rail uses buttons; "Words" is "Captions"), log (opens "Talk to the director" first), layers_media (Select, then Put on the timeline; sounds in the Audio tab; Position tab), engines and comfy (the engine cards are on the Server page; ComfyUI runs on the RTX 3060, not the V100), shot_sec (Settings shows one section at a time), shorts_swipe ("Moment 1 of 2", the Keep checkbox), journey (no "More options"; the name is on the last screen), settings_audit (`chromePath()`), motion (defaults to the scratch project's composition), journey's samples path (`client/../samples`).

No suite was retired: every feature they test still exists.
