# F6: many jobs — Done by codex

2026-11-06. Four regression tests in `tests/test_job_queue.py`.

Concurrent API calls checked for an existing job and registered a new job in separate operations. With twelve simultaneous requests, both reuse and refuse policies created twelve jobs. Both regression cases failed before the code changed (2 failed, 2 passed).

`JobManager.submit` now locks the busy check and registration together. Its queued notification precedes queue insertion, so a fast worker cannot announce completion before the initial queued notification. Collection readers use a locked snapshot instead of iterating a dictionary that API threads can change.

Checks cover simultaneous reuse and refuse requests (one job and one execution), two videos queued with thumbnails and an export (all results preserved, single-worker order), and cancelling a queued video without losing the next export. Related API busy/refuse and job-log tests pass. The later combined job/recovery/API/director selection run passed 20 tests with 56 deselected. No GPU, speech or video render was used.
