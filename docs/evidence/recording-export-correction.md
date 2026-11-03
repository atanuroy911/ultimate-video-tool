# Recording export correction — 2026-11-03

The owner rejected an added caption/graphics band. Recording modes now retain the selected 1920×1080 format and use the ordinary project caption style and grouping. No special recording caption theme or CSS remains. Motion graphics overlay the original video.

Validation: 26 focused recording, caption-editing, caption-style and composition tests passed; the Studio production build passed; all 23 timeline tests passed. Recording captions are compared against the same project's ordinary captions in both theme and pop modes.

The first full pipeline export failed visual QA: audio and captions advanced but the source picture stayed at frame zero. It was not accepted. The operator briefly provided its link before checking decoded frames, then explicitly withdrew it. The local failed file was moved into `dist/recording-acceptance/rejected/`; the remote batch quarantines that export under its own `qa-recordings/rejected/`.

Root cause: HyperFrames 0.8.181 scans inline JavaScript when deciding whether runtime media discovery is needed. Our video factory was only in an external script. With a known composition duration, the compiler skipped the browser probe, found zero videos, extracted no source frames, and encoded the initial video frame. Stable DOM video IDs fixed snapshots but were insufficient for full exports.

Fix: video compositions inline the actual `vt-media.js` factory so the normal compiler media-discovery path runs. All timed video occurrences retain stable unique IDs. No third-party dependency files were modified.

A real eight-second render uses source seconds 60–68. Decoded output at seconds 1 and 7 is compared with original seconds 61 and 67 at 480×270. Before the fix the comparison failed. After the fix it passed on Windows (mean absolute RGB errors 1.158 and 0.898) and on the Linux GPU server (1.158 and 0.897), on a 0–255 scale. Compiler logs confirm one discovered/extracted video after the fix, versus zero before it.

The active runner is `scripts/lab/recording_pipeline_worker.py`, launched with `scripts/lab/start_recording_edits.py --full-pipeline`. It invokes the product's `Pipeline.run()` and production `export()` for each of the four projects, rather than using the earlier manual project-preparation recipe. It uses existing stage caches, only the RTX 3060 for ASR, and at most four CPU browser workers for export. It checks source pixels at multiple points before publishing each export in `edits.json`. All remote files are under `/home/roy/ultimate-video-tool-server`; existing engines and unrelated training are not restarted.

At the time of writing, the corrected full batch has restarted. Four accepted exports are **not yet complete**. Runtime status is in `dist/recording-acceptance/render-status.json` after fetching; final acceptance must include decoded-frame inspection, duration/dimension/audio checks and inspection of the generated motion graphics. The separate plant QA project and queued research/planning tasks remain pending as recorded in `docs/ACTIVE-WORK.md`.
