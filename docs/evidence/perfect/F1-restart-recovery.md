# F1: restart recovery implementation — Done by codex

2026-11-06. The plan checkbox remains open until a real scratch-server restart is checked. The owner explicitly kept renders paused in this chat.

The app's queue now saves each public job record atomically to `projects/.jobs/<id>.json` before sending its event. Startup loads those records and marks queued/running jobs as interrupted errors, preserving their stage and a plain explanation. It never replays a callable automatically. A malformed record is logged and does not prevent recovery of the others. Writes that fail are logged without killing an active job.

Projects left Processing by the old memory-only queue also become interrupted and receive a recovered pipeline job. Newly interrupted queued pipeline jobs mark their projects interrupted too. Finished-stage hashes and outputs are preserved. The dashboard shows Interrupted and opens the recovery screen. Continue submits the ordinary pipeline with no forced starting stage; existing stage hashes/output checks determine what can be reused. Explicitly passing a starting stage would force later work, so Continue deliberately sends `from_stage: null, force: false`.

The WebSocket hello supplies the current job snapshot, including recovered errors. The browser replaces its stale running jobs with that snapshot and refreshes project data. Progress and hooks choose the newest jobs by creation time rather than random UUID ordering. The stopped screen has no live ETA or claim that processing continues.

Six Python tests in `tests/test_job_recovery.py` cover running/queued/completed records, writing progress before broadcasting, legacy Processing metadata and preserved stage state, malformed records, queued pipeline recovery, and Continue requesting the cached pipeline. Related queue/log/API/director tests passed (20 selected tests total).

`client/studio/e2e/job_recovery.mjs` serves the built Studio with fake HTTP and WebSocket responses. At 1280px/light and 400px/dark it verifies the interrupted state, Continue body, next-job selection, no sideways overflow, and no page errors. Both pass. Screenshots in `client/studio/e2e/out/job-recovery/` were viewed after animations completed. Studio TypeScript/build and 32 timeline tests passed.

Remaining: perform the real restart on a disposable scratch server. No deployment, owner-server restart, render or GPU work was performed. Job log history is still memory-only; recovered records retain status/stage/result/error, not the old detailed log. Retention limits remain F11.
