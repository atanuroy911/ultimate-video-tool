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
- First attempt: the runner sets `MAX_MCP_OUTPUT_TOKENS=200000` (`client/desktop/director-runner.js`). Not enough: the task is about 49,000 characters (about 12,000 tokens), well under that limit, and Claude still got a saved-file message sometimes. Claude Code saves any result above about 50,000 characters, a separate limit.
- Fix: every MCP tool now asks for the largest allowed result (`_meta["anthropic/maxResultSizeChars"] = 500000`, `RESULT_SIZE` in `server/vt/mcp/server.py`, tested in `tests/test_mcp_result_size.py`). Verified on the installed server: Claude read the task and submitted the script on the first try.
- Still open: when the chosen director finishes without a plan, the server falls back to another director without saying so loudly. That is by design ("best available") but for an explicitly chosen director the person should be asked first. Raise with the owner.

### F3. Every real Claude session was cut off after 120 seconds (fixed)
- After F2, Claude submitted the script three times and was looking at frames when the server cancelled it at exactly 120.1 s ("did not answer in time").
- Cause: the setting "When that computer is busy, wait" (default 120 s) was used as the total time allowed for a whole planning session.
- Fix: `directors.direct_timeout()` never gives a session less than 30 minutes (`DIRECT_MIN_SECONDS`), pipeline uses it in all three places; the settings page says so. Test: `test_a_planning_session_is_never_cut_short_by_the_busy_wait`.

### F4. Installed client could not start (fixed)
- A file added to the client (`server-keys.js`) was not in the installer's whitelist (`package.json` `build.files`), so the packaged app silently failed to start. New test `client/desktop/test-packaging.js` checks every loaded file is listed. Found only because the installed app was actually launched.

## First real video: `explainer-watch` (English, 9:16, explainer, Claude on this PC / Sonnet directing)
Made in 884 s (planning, with 56 AI conversations) + 64 s render; 30.1 s, 720x1280, with audio; no AI errors; `director_used` says `claude@a22c9b52`. Contact sheet: `E:\UltimateVideoTool\matrix\2026-11-20-claude\explainer-watch.png`. Good: on topic, one idea per scene, numbers shown big ("1/3", "2 days"), captions follow the voice. What a viewer would notice:

### F5. Empty screens
- "1. Always-on display" is a title at the top and a caption at the bottom with nothing between them for about 5 s (frames 4 to 6); the same for "3. App notifications" before its icon appears. Retention measured: see `results.json` (`empty_longest_s`).

### F6. Text printed over other text
- The "2. Heart rate checks" title, a "Constant checks" label and the "Every minute is enough" callout overlap in the middle of the screen (frames 8 to 10). The director's own look-and-revise step did not catch it (the one revision the plan allows). Per the owner's rule, the person fixes what is left by hand: this is a case for the timeline's per-element editing, and for the layout check to list it.

### F7. Unreadable colours and a meaningless picture
- "4. Bright screen outdoors" switches to a pale grey background and keeps the yellow label, which is nearly invisible (frame 13); the next frame is a blue and yellow checkerboard standing for "bright screen". The label colour does not follow the background the director picked.

### F8. Fifteen minutes for a 30-second video
- 884 s of planning on this laptop, most of it the director looking at frames (each `preview_frames` call renders in Chrome on the laptop and took 80 s or more). Worth measuring where the time goes before adding more AI steps.

These four are quality problems, not crashes: they belong to `docs/plans/PLAN-PERFECT.MD` (teach the director; never override it with code).

## The Claude usage limit, and what the local AI made instead (2026-11-21)

### F9. A video costs about 60 Claude requests, so the subscription limit ends a run after 2 to 3 videos
- The first run hit "You've hit your 5-hour limit" about 25 minutes in (2 videos made). Each video asks Claude about 30 small questions (pictures and meanings, 5 to 10 s each) plus a planning session of 8 to 56 tool calls. That is the real cost of "Claude directs", and it matters for anyone who uses a subscription.
- The server then handed every later video to the local AI **and installed it on this PC to do so** (Ollama and gemma downloaded into `ServerData`). The Studio did say so on each project (`ai_notice`: "Claude's usage limit was reached, so Local AI directed this video."), but a person starting a video with Claude chosen got a different director without being asked first. Raised with the owner: for an explicitly chosen director, ask before switching.
- The bench now stops at the first fall-back instead of producing videos with the wrong director (`local_matrix.py`, `--keep-going` overrides). Those 20 videos are kept as the local AI's results: `E:\UltimateVideoTool\matrix\2026-11-21-local-fallback\`.

### F10. What the local AI (gemma) made: wrong pictures and text over characters
Sheets in `2026-11-21-local-fallback\`. Examples:
- `stick-monday` ("snooze once", "jump out", "stop and watch", "your coffee"): the pictures above the figures are a moon cake, a number "8", a blossom and a handshake: words matched to the wrong sense (moon cake for *snooze*, a flower for *stop and watch*, a handshake for *friend* where the sentence is about a friend driving by). The two figures stand on top of each other for 12 of 18 frames.
- `cartoon-leaves`: a white quote text is printed over the two characters and cannot be read (frames 5 to 7); a repeated emoji "leaf" is a purple flower; one frame is a half-transparent grey panel over the scene.
- Two rows ended with "no plan yet" and were not exported: `reel-start`, `reel-banglish` (the reel director gave nothing back). Open.
These match the lab notes from 2026-10-31 (wrong lexicon senses, text over pictures). They belong to `docs/plans/PLAN-PERFECT.MD`.
