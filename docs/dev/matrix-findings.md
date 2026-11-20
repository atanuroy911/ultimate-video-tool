# Matrix findings

Found by `scripts/lab/local_matrix.py` on the installed 0.5.0 server on this laptop (Windows, RTX 4050, Claude on this PC as the director). Newest first. Each finding: what happened, the project, what was done.

## 2026-11-20

### F1. The server process died in the "Listening for sounds" step, and nothing restarted it
- First row (`explainer-watch`, English, 9:16, Claude directing), first server start after setup. The log showed `Could not load symbol cudnnGetLibConfig. Error code 127`, then `Processing server exited 3221226505` (0xC0000409). The matrix client got a connection reset. The server manager window stayed open with the server stopped.
- Environment: torch 2.6.0+cu124 (cuDNN 9.1 in `torch/lib`), ctranslate2 with its own `cudnn64_9.dll`, onnxruntime-gpu 1.26.0.
- Not reproduced: the same stage run alone in the installed environment (with and without the GPU fence, with ONNX Runtime loaded first) works, and the same row passed the stage on the second server start.
- Two separate problems: (a) an intermittent native crash in a library mix (suspect: a second `cudnn64_9.dll` loaded by name from CTranslate2's folder before torch's own); (b) the server manager does not restart a crashed server, so a person just sees nothing work. Fix (b) for sure (restart with a back-off and say so in the window). For (a), preload torch's `cudnn64_9.dll` by full path in `vt.gpu.prepare()` on Windows, so a by-name load from another package reuses it.
- Status: open.

### F2. Claude's planning task was too big to arrive, so Claude never planned (fixed)
- `explainer-watch` with Claude: Claude called `get_script_task`, then tried `Bash`, `PowerShell` and `Read` (all refused: the planning session has no built-in tools), and finished "successfully" with no plan. The server then silently fell back to the local AI and started downloading it.
- Cause: Claude Code saves an MCP tool result above its size limit to a file and tells Claude to read it. The task (rules, schema, every timed word) is that large.
- Fix: the runner sets `MAX_MCP_OUTPUT_TOKENS=200000` for the planning session unless the person set it (`client/desktop/director-runner.js`, tested in `test-director-runner.js`). With it, Claude submits the script.
- Still open: when the chosen director finishes without a plan, the server falls back to another director without saying so loudly. That is by design ("best available") but for an explicitly chosen director the person should be asked first. Raise with the owner.

### F3. Every real Claude session was cut off after 120 seconds (fixed)
- After F2, Claude submitted the script three times and was looking at frames when the server cancelled it at exactly 120.1 s ("did not answer in time").
- Cause: the setting "When that computer is busy, wait" (default 120 s) was used as the total time allowed for a whole planning session.
- Fix: `directors.direct_timeout()` never gives a session less than 30 minutes (`DIRECT_MIN_SECONDS`), pipeline uses it in all three places; the settings page says so. Test: `test_a_planning_session_is_never_cut_short_by_the_busy_wait`.

### F4. Installed client could not start (fixed)
- A file added to the client (`server-keys.js`) was not in the installer's whitelist (`package.json` `build.files`), so the packaged app silently failed to start. New test `client/desktop/test-packaging.js` checks every loaded file is listed. Found only because the installed app was actually launched.
