# F7 input boundaries — Done by codex

2026-11-06. Local isolated tests on Windows, with processors replaced. No real GPU, model, recognition, render, owner-server call or download ran.

Changes:

- Personal SRT/VTT files are parsed by complete subtitle blocks. Invalid arrows, negative or invalid clocks, reversed/zero cue durations, missing text and malformed later blocks return a plain error naming the block. Invalid UTF-8 gives a save-as-UTF-8 instruction. Validation finishes before any subtitles or project metadata are replaced, so a bad replacement preserves the working subtitles. Valid VTT headers, comments, style metadata, cue identifiers/settings, UTF-8 names and Bangla text remain supported.
- Wrong-shaped downloaded JSON captions return the existing `None` fallback instead of leaking `AttributeError`/`TypeError`; the normal speech stage can take over.
- A shared `read_subtitles` preflight now runs before the upload API creates a project. The original orphan-project failure was reproduced separately (`1 failed, 1 passed`): a malformed subtitle returned 400 but left a draft. The fixed route validates first and reuses the same temporary file for attachment, so rejection creates neither a project nor a job. Valid subtitle uploads still attach their exact words.
- Known FFmpeg decode failures at preprocessing become `InvalidRecordingError` with a plain instruction to play/export/replace the recording. The pipeline records `error`, leaves preprocessing uncompleted, and allows a successful retry. Disk/tool/infrastructure failures retain their actual error. Existing cancellation handling was preserved.
- Windows project names ending in dots now use a slug matching the real folder, including a dot introduced at the 40-character truncation boundary. Display titles retain the original Unicode/punctuation and duplicate names get separate folders.

Regression-first result: the first new-file run showed **16 failed, 10 passed**. Real failures covered silently accepted malformed subtitles, a bad replacement overwriting good subtitles, replacement characters instead of an encoding error, wrong-shaped downloaded JSON caption exceptions, raw decoder command errors, and the Windows `...` folder mismatch. One of the 16 failures was a missing fake sound-caption hook in the new two-hour test, which was corrected separately; it was not a production bug.

Checks (working directory `server`, repository `.venv`):

```text
..\.venv\Scripts\python.exe -m pytest -q -c NUL --rootdir=.. ..\tests\test_bad_input.py
28 passed, 6 warnings in 30.13s

..\.venv\Scripts\python.exe -m pytest -q -c NUL --rootdir=.. ..\tests\test_ingest.py -k 'not api' ..\tests\test_pipeline_cancellation.py
28 passed, 2 deselected, 6 warnings in 20.57s

# Final combined run after the upload preflight code edit:
..\.venv\Scripts\python.exe -m pytest -q -c NUL --rootdir=.. ..\tests\test_bad_input.py ..\tests\test_ingest.py ..\tests\test_pipeline_cancellation.py -k 'not the_api_validates and not unsafe_or_broken_links'
51 passed, 9 deselected, 6 warnings in 50.62s
```

Warnings are the existing FastAPI `on_event` deprecations. The final run includes all 30 new F7 cases, the existing caption/parser/fake-link cases and the existing cancellation regressions. Its selection excludes the existing lifecycle API test and eight DNS/link cases, keeping this check free of discovery services and network resolution; the new API cases use fakes without app lifespan. The earlier API-name filter also excluded the URL parameter containing `/api`. No test was disabled or weakened.

Coverage of all six F7 inputs:

| Input | Checked |
|---|---|
| Corrupt file | Fake decoder errors for invalid media, missing MP4 metadata and missing audio; plain error, error state, no completed checkpoint/scene, then successful retry. |
| Silence | Fake recognizer returns no words for four seconds of silent metadata; the existing microphone/file instruction is raised, state is `error`, no raw transcript or scene is written. |
| Two hours | Duration metadata drives the real ASR chunk planner and pipeline bookkeeping, with a fake recognizer: 480 overlapping windows, each at most 15.301 s, covering 0–7200 s. No new upload duration cap was added. Links retain the existing 60-minute download cap. |
| Wrong SRT | Invalid clocks/arrows/order-within-a-cue/empty text/mixed valid-invalid blocks/encoding and preservation of existing assets, plus valid VTT/Bangla compatibility. |
| One-word script | `Hello!` passes a fake voice stage into the typed-word ASR branch without recognition, then the real transcript/beat/rule-scene builders produce one valid scene. |
| Unusual names | Unicode/emoji/Japanese/Bangla, path-like punctuation, `CON`, all dots, trailing dots, truncation and HTML-like titles stay in the temporary project store; metadata preserves the title. |

Limits: these tests prove input handling and failure/retry bookkeeping with fakes, not real decoder behavior, real ASR accuracy, long-recording memory/performance, voice quality or a finished video. The two added upload API tests run in-process with a fake source inspector and without lifespan/discovery services. Real heavy processing remains paused by the owner.
