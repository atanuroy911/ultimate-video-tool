# Ultimate Video Tool — handoff to Claude

Updated 2026-11-03. Workspace: `C:\Users\Roy\Desktop\ultimate-video-tool`.

## CURRENT STATE: 2026-11-03 night (this section supersedes the STOPPED notice below)

The owner lifted the stop and gave new work: clean up both machines and set Video Tool up again as a normal user, run recording 2 through the whole pipeline with
music on the GPU server and judge the edit, fix the real errors, make the client UI coherent (using the `ui-ux-pro-max` skill), show server load and let the owner
choose the GPU per job. **Still true: no commits or pushes; no Co-Authored-By lines; processing runs on the GPU server only (never launch renders or GPU tests on
this Windows PC; the render tests pass `gpu=False`).** Password for the server (`roy@192.168.123.47`) is given by the owner per session and passed as `GPU_PASS`;
it is never written to a file.

### What was cleaned and reinstalled (and what was not touched)
- **GPU server:** only `/home/roy/ultimate-video-tool-server` (31 GB), its user service, autostart entry and Applications entry were removed, then installed fresh from a
  newly built package (`dist/fresh-2026-11-03/video-tool-engine-1.0.0.tar.gz`) by `scripts/lab/install_server_fresh.py`: Python 3.11 with the **cu124** GPU build chosen
  by `vt/gpu_detect.py` (the installer used to install the CPU build), a checksum-verified private Node 22, renderer packages, `run-server.sh`, user service
  `ultimate-video-tool.service` (port 8790; existing ComfyUI 8188 and Ollama 11434 are used), and the native manager with its **Applications entry** (GTK window,
  `scripts/lab/install_server_manager.py`; it does not open a window by itself). **Not touched:** ComfyUI/Ollama, `/mnt/bigdata/*` (including the older
  `/mnt/bigdata/video-tool-server`), the SSD models, the owner's training on the V100, ports 8765/8766/8777.
- **This PC:** the two old apps and the Windows server edition's private data folder were removed (exact paths only), the client was rebuilt and installed from
  `dist/fresh-2026-11-03/client/Ultimate-Video-Tool-1.0.0-win-x64.exe` (built with `signAndEditExecutable=false` because this account cannot create the symlinks the signing tools
  need; the exe therefore has Electron's default icon/metadata). Installed to `%LOCALAPPDATA%\Programs\Ultimate Video Tool`, data in `%APPDATA%\Video Tool`.
  **Launching from the VS Code terminal needs `Remove-Item Env:ELECTRON_RUN_AS_NODE`**, otherwise Electron runs as plain Node and exits at once.
  The silent uninstaller removes shortcuts but leaves the program files (a real bug to test with the GUI uninstaller).

### GPU facts
- **Tesla V100 (GPU 0) is the owner's; Video Tool must not use it.** The RTX 3060 (GPU 1) is ours. `run-server.sh` no longer pins `CUDA_VISIBLE_DEVICES`; instead the
  saved setting `gpu.primary` = the 3060's UUID (`GPU-a1b5ab18-d194-1ae3-a17f-4561c4f0cd7d`) decides, and `CUDA_DEVICE_ORDER=PCI_BUS_ID` keeps numbering equal to `nvidia-smi`.
- ComfyUI 8188 runs on the 3060 (owner's service; the owner restarts it), Ollama is pinned to the 3060 (`OLLAMA_LLM_LIBRARY=cuda_v12`).
- **Rendering does use the 3060** (verified in the render's own report and by sampling `nvidia-smi`: `chrome-headless` processes on GPU 1, 16-33 % during capture; NVENC has a
  separate encoder counter). The owner could not see it because browser capture is a light graphics load and the V100 showed 90+ % from their own job.

### Built in this session (all uncommitted; tests in `tests/test_gpuassign.py`, `test_handback.py`, `test_engine_fit.py`)
| Feature | Where |
|---|---|
| System stats: processor, memory, disk, every GPU, per-program load (graphics programs too), which engines run where | `server/vt/sysstats.py`; `GET /api/system/stats`; `vt system [--watch]`; MCP `system_stats`; Studio `components/SystemStats.tsx` (live, "Updated N s ago", Pause, stale state, one `role=status` line) |
| GPU assignment per job (rendering, speech recognition; primary card or automatic = freest); ONNX voice paths follow the card | `server/vt/gpuassign.py`; `GET /api/system/gpus`, `PUT /api/system/gpu`; `vt gpu`, `vt gpu set render 1`; MCP `gpu_assignment`; Studio `components/GpuAssignment.tsx`. Ollama/ComfyUI are shown, not switched (separate programs) |
| New **Server** page + nav item; **Settings cut to 5 sections** (Preferences, Voice & speech, Directors & assistants, Picture libraries, Help & checks), deep links `/settings?s=directors`; "Director" wording everywhere; the Director pill shows the director that will actually be used first; the directors list says when "Claude on this PC" is not connected; legacy terminal-command cards removed | `client/studio/src/pages/Server.tsx`, `Settings.tsx`, `Shell.tsx`; plan in `docs/plans/PLAN-CLIENT-UX.MD` |
| One server name in the setup banner (the server's own `--name`, not the hostname) | `server/vt/engines/setup.py` |
| A finished video that is only exporting opens the **editor**, not Progress/Result | `client/studio/src/pages/Projects.tsx` (`isBeingMade`), `Review.tsx` |
| Client command line: `"Ultimate Video Tool.exe" --server <url> --code <pairing code>` | `client/desktop/main.js`. `--server` works (also hands over to a running app). The `--code` pairing step is **unverified**: a launch with `--code` logged nothing; the new build logs "Command line: ..." so read `%APPDATA%\Video Tool\desktop.log` |
| Safe downloads (never truncates the local file); download helpers use it | `scripts/lab/safe_get.py` |
| `large-v3` is the English speech model whenever a GPU exists (downloads itself, ~3 GB) | `server/vt/stages/asr.py` |
| Linux loads pip-installed cuBLAS/cuDNN by path so GPU transcription works | `server/vt/gpu.py` (`_load_linux_cuda_libs`) |
| **A no-face picture video (screen recording) defaults to the protected "subtitles" mode** (own picture and pauses, captions, music); graphics are the explicit "screen" choice | `server/vt/source_inspect.py` (`default_recording_edit`), applied in `server/vt/server/app.py` `create_project` |
| Steps row no longer runs words together ("TricksBooks") | `server/renderer/runtime/vt-info.css` |

### Judgement of recording 2, first run (default "auto" = the whole explainer treatment): NOT a proper edit
`dist/recording-run/2026-11-03-recording-2---full-pipeline-with-music-16x9-20261103-230044.mp4` (341.9 s, 1080p30, -14.2 LUFS; transcription of the 357 s recording took ~30 s on the 3060).
Good: the screen picture and narration kept, captions in the normal pill, music present. Bad (all measured or seen): **6 black flashes (0.1-0.17 s)** at 5.9, 40.9, 117.6, 157.9, 305.7, 327.5 s
that are not in the original (fade transitions); **a glitched wipe frame** (screen drawn in strips over cream) at ~75 s; a **full-screen cream "Tips Tricks Books" card** at the end covering the
recording; 45 of 49 scenes had a random transition, 32 keyword badges and 18 stickers on a tutorial. Cause: `recording_edit="auto"` ran the generic explainer planner. Fixed by the default above.
**Second run (all defaults) was started at ~23:33 on the server: log `dist/recording-run-v2/run.log`, project `2026-11-03-recording-2---v2-protected-default` (it resolved to `subtitles` by itself).
Judge it the same way: black-frame check (`ffmpeg blackdetect=d=0.1:pix_th=0.12`; the original has none), contact sheet, loudness, music vs speech.**

### Open, in order
1. Judge run v2 (above). If transitions/overlays still appear, fix; then try `--edit screen` and judge the restrained graphics (no full-screen card over a text-heavy screen).
2. Verify `--server --code` end to end (rebuild logs it), then record the result here.
3. Deploy rule: `scripts/lab/deploy_server_code.py` refuses to restart while a job runs; run it only when idle.
4. Re-test the server manager's Applications entry on the server's screen; test the Windows GUI uninstaller (the silent one is incomplete).
5. Everything in `CODEX-HANDOFF.md` "Tasks, in order" that is still open.

### Traps met today
- `python3 -` typed in front of a heredoc swallows the script and hangs the shell: never write it.
- Heredoc/`sed` turned regex `\b` into a literal backspace in `.py` files (check with the one-liner in CODEX-HANDOFF); use the editor or a script file.
- Vite's dev server can serve a stale copy of a file: restart it before judging a screenshot (`VT_SERVER_URL=http://192.168.123.47:8790 npx vite --port 5173`).
- The server's connected-director list is in memory: after any server restart "Claude on this PC" disappears until the desktop app reconnects.

## EARLIER STOP NOTICE (superseded by the section above; kept for the record)

The owner's latest instructions are **“stop everything,” “write all changes to CLAUDE-HANDOFF.md,” and “stop all sorts of coding… just document.”** Those instructions supersede earlier requests to continue. Do not resume coding, builds, tests, renders, installations, cleanup, downloads, or the historical task queue without a new instruction from the owner. This document records the current state; it does not authorize continuation.

The remote recording QA process tree was stopped. The local Vite development server, PID 42580, was stopped. The remote batch status now says `stopped-by-owner`; its last active stage was content analysis for the second recording's motion version. No renderer batch was intentionally left running. Existing installed Video Tool/ComfyUI/Ollama services were not uninstalled or shut down as part of stopping this work.

The owner requested project cleanup before clarifying “just document.” Only an inventory was performed. **A comprehensive filesystem cleanup was not executed.** Do not claim the directory has been cleaned. No Git reset, clean, checkout, commit, push or release was performed.

## Critical facts and failures

1. **Current processing authorization is the remote server `192.168.123.47`, under `/home/roy`.** The client's Windows GPU is not authorized for this work. A production requirement to use available GPU acceleration applies to the selected processing server, not permission for an agent to launch work on every accessible computer.
2. An eight-second-segment GPU test export was mistakenly launched on this Windows PC's RTX 4050. The owner objected. Its session had already exited successfully when checked; no matching local test process remained. The mistake was acknowledged. Do not repeat a local GPU test without explicit permission.
3. A preliminary remote hardware test correctly pinned NVENC to RTX 3060 but let the browser choose V100. That short test ended. Browser selection was then fixed and a subsequent real probe explicitly identified RTX 3060/Vulkan. Do not rewrite this history as if every test used only RTX 3060. Existing training services were not restarted.
4. **Completed video deliverables are currently unavailable.** At the stop-time read-only inventory, `/home/roy/ultimate-video-tool-server/data/projects` was empty. The cause was not established. Do not attribute this to the owner or assert that project deletion was an intentional cleanup action.
5. The download helper used `sftp.get(remote, local)` directly. When remote MP4s were missing, failed downloads truncated the existing local MP4 destinations. This is a serious helper bug. It was disclosed to the owner. A catch was added to report missing references, but **atomic download replacement has not been implemented**. A future authorized fix must stat the remote file, download to a separate temporary file, verify it, and only then replace an existing destination.
6. The two original recordings were not modified by this work and remained in the repository root during the final inventory. Code, source recordings, documentation, subtitle files, status/manifest files and QA PNGs were not deliberately removed by a cleanup pass.

### Actual output state at stop

Before the missing-directory/download failure:

| Requested result | Processing reached | Verification before loss |
|---|---|---|
| Recording 1 — subtitles | Full product pipeline and export completed | Source pixels checked at 5/65/150/280 seconds, two decoded frames visually inspected, full decode passed; 1920×1080 H.264/AAC, 30 fps, 310.533 seconds |
| Recording 1 — baseline motion graphics | Full pipeline and export completed | Four automatic animated text callouts; source checks, actual output frames and full decode passed; same dimensions/duration |
| Recording 2 — subtitles | Full pipeline and GPU export completed | Remote source-picture comparisons passed; no final manual visual/full-decode acceptance was completed before stop |
| Recording 2 — baseline motion graphics | Stopped during content analysis | Not exported |
| Recording 2 — original picture plus music | Queued after the four edits | Not started |

Now:

- `dist/recording-acceptance/exports/1-subtitles.mp4`: **zero bytes, invalid**.
- `dist/recording-acceptance/exports/1-motion-graphics.mp4`: **zero bytes, invalid**.
- `dist/recording-acceptance/exports/2-subtitles.mp4`: **zero bytes, invalid**.
- Recording 1 SRTs and actual output PNGs remain in that directory. Other QA images, transcripts and logs remain under `dist/recording-acceptance/`.
- `edits.json` still references three previously completed remote exports, but those paths failed SFTP stat/download at stop. A successful historical manifest entry is not evidence that a file exists now.
- The known rejected frozen-picture MP4/SRT remained in remote `qa-recordings/rejected/` at the read-only inventory. That failed video is not a substitute deliverable.
- Do not offer the zero-byte MP4 links, claim four videos were delivered, or silently rerender after the stop instruction. Recovery/recreation requires renewed authorization.

## Owner's product vision and constraints

- Product name: **Ultimate Video Tool**.
- Simple, tidy, responsive workflows with understandable labels. Advanced capabilities should be organized and explained plainly rather than hidden or multiplied across competing screens.
- A single editable timeline. Every built scene, component, caption, sound and voice region should remain editable, with immediate preview updates, accurate split/trim/drag timing and reliable undo.
- Client and server are independent products. The processing server must not contain the editor workspace.
- Native server management on Windows and Linux: Applications/Start entry, useful controls and tray/status behavior. Engine settings and logs stay inside the native app, with Back navigation; do not unexpectedly open a browser.
- Windows uninstall distinguishes keeping environment/data from explicitly removing the edition's private environment/data. Independent existing engines and external custom storage must be preserved.
- Use the best available models/voices by default and show friendly names with provider/model detail where helpful. Imported recordings retain their original narration.
- **Use usable GPU acceleration automatically on the selected processing machine.** Production QA must exercise the real production path. Do not force CPU to avoid solving GPU selection. Any fallback needs an explicit reason and evidence of what actually ran.
- Remote installation/changes are confined to `/home/roy`; reuse existing ComfyUI and Ollama. Do not restart/replace unrelated engines or training. Do not write credentials into handoff files or source.
- The owner explicitly asked to finish queued work in order rather than switching to each new request. The queue below is historical and currently stopped.

## Current architecture and physical source split

```text
client/
  desktop/       Native client, local UI transport, Claude/Codex companion
  studio/        React editor, creation, timeline, Shorts, sharing, settings
server/
  desktop/       Independent native processing-server manager/bootstrap
  vt/            Python processing, API, Director, modules, rendering driver
  renderer/      HyperFrames/GSAP/Three.js runtime and dependencies
  assets/        Processing media/workflows/catalogues
  design/        Themes, fonts, icons, textures
  packaging/     Headless/bootstrap installation resources
  pyproject.toml
  uv.lock
```

Root `pyproject.toml` is test configuration, with Python import path `server`. The root `.venv` was retained as the existing development/test environment. The physical move did not imply moving or deleting user projects/settings/models. Many old root paths appear deleted and the new product directories appear untracked in the large, uncommitted working tree. Do not interpret that as permission to run `git clean` or restore the old combined layout. `git diff` alone omits untracked product code.

The native client serves its own UI locally. API calls, media range requests and WebSockets go to the selected processing server. Its loopback transport uses a session secret, strips that secret when forwarding, and uses separate Electron partitions for processing-server pairing. The client ships `ws` as its only production npm dependency, without the server's Python environment or renderer/model stack.

The client retains a small native Claude/Codex companion regardless of where processing is installed. Assistants register independently, reconnect, refresh readiness, cancel when the selected server changes and authenticate to that server's Director broker. The GPU server need not have the owner's Claude/Codex login installed. Server selection, pairing and assistant ownership are distinct concepts.

The processing server owns project data and work execution. Its `/` and `/manage` serve management pages; there is no editor SPA fallback for `/new`, `/settings` or project routes. The server distribution excludes Studio. The Linux manager uses GTK/WebKit on this host; Windows uses its own native Electron manager. Embedded engine pages cannot invoke native manager IPC. Engine settings/logs open internally, not through an external browser.

Before stop, client dev UI was `http://127.0.0.1:5173`, proxying `http://192.168.123.47:8790`. **Vite is now stopped.** Older `:8878` instructions in existing notes are historical. Do not restart either port just because an older handoff says it is running.

Remote installation: `/home/roy/ultimate-video-tool-server`; processing API `:8790`; existing ComfyUI `:8188`; Ollama `:11434`. The private Video Tool user service was updated during authorized work. This is separate from existing engine services. The remote data/projects directory being empty is a later unresolved state, superseding earlier screenshots showing projects.

## Setup, installation, packaging and server UI work

Implemented/reworked in earlier continuations:

- Discover existing engines on the selected server before offering managed installations.
- Server identity and “this server” labels, server-native absolute storage validation, separate installation/model roots and GPU choice.
- Four-step setup: server/engine choices, storage, connect/install, checks. Missing-model and workflow preparation is offered for existing installations.
- Existing ComfyUI downloads are constrained to folders it indexes. An arbitrary new storage root requires a managed installation; setup must not silently reconfigure an external engine. Existing Ollama owns its storage; managed copies support a chosen root.
- Independent client/server Windows manifests, locks, packaging and update/bootstrap fingerprints. Same-version upgrades compare source fingerprints before reusing a processing runtime.
- Native server manager Applications/Start entries, internal engine/settings/log navigation, port-occupation safeguards, user-level launch behavior and independent uninstall boundaries.
- Windows bootstrap/uninstaller logic preserves environment/data by default; explicit full removal targets only the relevant private edition folder and preserves external engines/custom folders.
- `scripts/dev-install.ps1`, `scripts/dev-install.sh` and shared `scripts/dev-install.mjs`: roles client/server/both; install/update/launch/check; private Node/uv/Python roots; vendor-checksummed Node fallback; role-specific dependency installation; client build; native launchers; fast-forward-only Git updates; dirty-checkout protection; four-hour update checks; isolated development state/data; JSON readiness output.
- CI/release definitions use independent roots and avoid bundling server resources into the client. **No GitHub release or push was performed.**

Important packaging artifacts observed during the final inventory:

- `client/desktop/dist/Ultimate-Video-Tool-1.0.0-win-x64.exe` — approximately 82 MB.
- `server/desktop/dist/Ultimate-Video-Tool-Server-1.0.0-win-x64.exe` — approximately 237 MB.
- Their blockmaps and unpacked builds remain. They are unsigned and predate the latest recording/GPU changes. Do not describe them as containing every change in this handoff.
- Older combined-product artifacts/snapshots are under `dist/legacy-combined/`; they are not the current product boundary.
- `server/packaging/engine/check-engine.py` and install-script delegation were added to avoid accepting an unrelated service on an occupied port and to stop only the helper's own child. Meaningful lifecycle and fresh installation acceptance for this latest helper remain pending.

Earlier acceptance is recorded in `docs/evidence/product-split-acceptance.md`, `docs/evidence/client-server-acceptance.md` and `docs/DEVELOPMENT-INSTALL.md`. Those are historical focused checks, not current production certification. Clean Linux native package installation, all native tray/uninstall clicks, clean server dependency installation and published-release acceptance remain incomplete. Developer scripts documented a locked CPU dependency installation; **automatic GPU-runtime provisioning needs a separate authorized production audit**, not an assumption that renderer GPU selection also repairs every AI environment.

## Editor, UI and reusable capability changes

Earlier working-tree changes include:

- Editor opens with the app sidebar collapsed; navigation can be restored. Focus/side-panel controls, clearer tool tasks, selection details and responsive wrapping preserve more canvas/timeline space.
- One timeline supports scene/component/sound/word/voice editing, precise time/range fields, split/trim/source offsets, fade clamping, track locking, release-coordinate saves, Escape/cancel behavior, save-race protection and consistent undo/redo.
- Scene boundaries follow actual sentence boundaries rather than silently snapping a cut to a nearby location. Scene-edge previews update both neighbors.
- Caption text and timing feed the live preview before the server save returns. The old WALK/RUN mismatch was traced to composition failure when an automatic theme disappeared. `Project.theme()` now keeps/reconstructs a project-local theme snapshot, and caption edits recompose all formats.
- Video-settings navigation returns to selected-element details. Dropdown backgrounds and compact tool navigation were repaired. Library elements have previews/examples; component templates, motion controls and media insertion use canonical editable data.
- Shared keyframes, entrances, transitions, camera recipes and text treatments drive the same preview/export runtime. Layer and component timing remains independent of the original scene duration, including split continuity.
- Direction panel exposes per-scene instructions, Director/model choices, actual generation history/provenance and picture/video/voice regeneration. Revision checks preserve intervening edits and make conflicting generated media available without overwriting newer work.
- Scene voice replacement preserves the cut clock, scene timing and anchored components, with bounded time fitting and one undo restoring audio/mutes/captions. It uses existing word anchors; it is not a claim of fresh forced alignment of every replacement utterance.
- Share uses selection-first flow, explicit export readiness and named account forms. Shorts uses a source/picks/edit workflow. Actual OAuth and real social publishing acceptance were not completed.
- Reusable animated shorts: three character treatments, ten environments, timed poses/expressions, generated-image props, environmental text and optional original procedural Three.js sets. Story planning is adapted into editable canonical components.
- Director/module discovery exposes component schemas, story/motion capabilities and generation controls. Long-form autonomous quality and “every capability is intelligently used” are not established by schema/contract tests.

External references included Concat, Filmcraft, HyperFrames, stick/cartoon/motion skills, `mromidev/claude-animated-shorts`, and the awesome Claude video-skills list. Research snapshots live in `docs/research/video-skills-2026-11-03/`. An inventory of 412 unique GitHub links is **not** 412 integrated capabilities. HyperFrames remains the renderer. Arbitrary external agents, hosted services, Remotion-only compositions and Lottie editing have not all been ported.

Details and older evidence: `docs/AUDIT-SKILLS-DIRECTION-2026-11-03.md`, `docs/AUDIT-2026-11-03.md`, `CODEX-HANDOFF.md` and `WORKLOG.md`. Some statements there are superseded, particularly ports, in-memory-only Direction draft recovery, installer freshness and video file availability.

### Direction recovery added during the recording work

- New `client/studio/src/review/directionDrafts.ts` persists drafts and active generation IDs in per-tab session storage, scoped to processing-server identity plus project/scene.
- Validates stored data, handles corrupt/unavailable storage and keeps revision-conflict behavior. Saving/reloading clears appropriate recovery data; a missing generation job releases a stale busy state.
- `DirectionPanel.tsx` restores those drafts after browser reload.
- `client/studio/tests/direction-recovery.test.mjs`: three passing cases. A disposable plant project's unsaved instruction was visually restored after an actual reload.
- This was built/tested in development, not included in a freshly rebuilt installed client.

## Recording task, implementation and mistakes

Original inputs in the project root:

- `2026-11-02 09-07-50.mp4`: 310.550 seconds, 1920×1080 H.264 at 60 fps, AAC 48 kHz; approximately 83 MB.
- `2026-11-02 09-13-35.mp4`: 357.200 seconds, same dimensions/codecs/frame rate; approximately 111 MB.

The owner confirmed separate videos, two versions each: subtitles only, then motion graphics appropriate to the narration. These are narrated desktop/PDF/browser demonstrations; figures, text and controls should remain usable. The original recordings were not to be replaced or cropped carelessly.

Both initial large-v3 transcripts completed on the remote RTX 3060. Missing cuBLAS/cuDNN initially blocked transcription; vendor runtime packages were installed **inside the isolated QA folder**, not into ComfyUI or unrelated environments. This is not proof that the normal server service's CUDA dependency setup is complete.

An unrequested added display band was introduced, extending the canvas for captions/graphics. The owner explicitly rejected it. It has been removed from code: no recording-specific caption theme/CSS, no eight-word special grouping and no added canvas height. Recording projects use the ordinary caption path; the QA examples selected the existing pop caption preset.

Initially, custom projects/manual reviewed annotation anchors and snapshots were prepared instead of running the complete app pipeline promptly. The owner objected to delays and partial work. The active runner was then changed to invoke the actual `Pipeline.run()` followed by production `export()`, with stage caches and editable generated plans. The earlier custom preparation runner is not evidence of end-to-end pipeline acceptance.

### Source-preserving recording mode

Key files:

- `server/vt/screen_recording.py` — recording layouts/base plan and narration-grounded supporting graphic proposals. It does **not** implement window/cursor detection.
- `server/vt/schema.py` — `recording_edit`: auto/subtitles/screen.
- `server/vt/pipeline.py` — protected recording paths preserve pauses, skip destructive automatic tightening/filler/retake removal, retain deliberate manual cuts and make the recording plan when no existing scene plan exists.
- `server/vt/aroll.py` — original-picture fast copy for a whole preserved recording; recording mode participates in stage signatures. The general fast-copy path still needs a browser-codec compatibility audit for non-H.264/MP4 sources.
- `server/vt/compose/composer.py` — ordinary caption behavior, source-preserving layout and runtime media discovery integration.
- `server/renderer/runtime/vt-media.js`, `vt.js`, `vt.css` — full source picture without face punch-ins/text-band crop; stable unique video IDs; removal of the rejected special caption CSS.
- Client `pages/New.tsx`, `types.ts`, `review/Preview.tsx`, `pages/Review.tsx` — recording choices and authoritative preview dimensions. No extra band remains.

Supporting graphics currently propose restrained keywords/steps using exact narration quotes. The actual first motion plan produced four text callouts. **The owner considers text-over-text a poor approach for this material.** It is a baseline experiment, not acceptance of an excellent final creative style. The requested full-screen cutaway approach is deferred below.

### Frozen-picture export bug — fixed and reproduced

Snapshots looked correct, but the first full MP4 held the source's opening wallpaper while captions advanced. That MP4 was initially linked too early, then explicitly withdrawn and quarantined.

HyperFrames 0.8.181 scans inline scripts to decide whether runtime media discovery is necessary. With a known duration and only an external video factory, the compiler skipped its browser probe, discovered zero videos and extracted zero source frames. Adding stable DOM video IDs fixed snapshots but did not fix this full-render path.

Video compositions now inline the **actual** `vt-media.js` factory. Normal renderer discovery can see timed video elements and extract/inject their frames. No third-party dependency source was patched.

An eight-second actual render of original source seconds 60–68 compares output seconds 1 and 7 with original seconds 61 and 67. It failed before the fix and passed afterward on Windows and Linux. Initial CPU comparisons were approximately 1.158/0.898 mean absolute RGB error at 480×270; subsequent correctly selected remote GPU comparisons were approximately 1.154/0.885. These are source-picture checks, not subtitle transcription accuracy scores.

### ASR fallback — implemented, environment acceptance incomplete

`server/vt/stages/asr.py` now catches specific CUDA/cuBLAS/cuDNN failures that occur lazily during decoding, not only model construction, and retries once on CPU with a progress message. Unrelated failures still propagate. `tests/test_asr_runtime_fallback.py` had three passing cases.

The owner's later GPU requirement means missing GPU libraries must be diagnosed/repaired properly in production. A working CPU fallback is not permission to leave a usable GPU unconfigured. No complete clean-machine GPU environment acceptance was performed in this final work.

## GPU acceleration changes

Normal `Pipeline.export`, API export body and module export defaults were already GPU-enabled. The recording QA runner incorrectly overrode them with `gpu=False`; that override was removed. The owner explicitly objected.

Latest code changes:

- `server/vt/render/browser_gpu.py`: query NVIDIA cards; respect explicit CUDA UUID/index selection; test real NVENC initialization rather than only FFmpeg's compiled encoder list; select a usable card; pin CUDA encoding. When NVIDIA is unavailable, leave HyperFrames' AMD/Intel/Apple hardware checks available rather than forcing CPU.
- `server/vt/render/chrome_gpu_launcher.py`: Linux launch adapter uses Vulkan so ANGLE's physical-device preference selects the same intended GPU. Explicit software diagnostic flags are preserved. The adapter is invoked through a generated private launcher in the composition's `.renderer` folder.
- `server/vt/render/hyperframes.py`: use available acceleration; capture the actual browser probe; save acceleration JSON and render logs; report a reason through progress when GPU rendering fails/falls back. CPU fallback still exists, but it is no longer supposed to be silent.
- `server/vt/pipeline.py`: copy the renderer acceleration report next to the final MP4.
- `server/vt/server/app.py`: expose export acceleration reports; exclude hidden incomplete `.render-*.mp4` files from normal export listings.
- `client/studio/src/pages/Export.tsx`: acceleration is automatic instead of an opt-out “faster” checkbox. It no longer equates missing NVIDIA/CUDA detection with proof that no GPU exists. Export details show the selected card, actual browser probe and warnings inside the app.
- `client/studio/src/types.ts`: export acceleration metadata.
- `tests/test_render_acceleration.py`: unsupported-card selection, UUID/index selection, Linux argument behavior, visible fallback/reporting and hiding incomplete exports.

Real remote evidence:

- A standalone NVENC test identified **NVIDIA GeForce RTX 3060**, initialized NVENC 13.0 and encoded successfully with CUDA device visibility pinned by UUID.
- The first browser GPU test selected **Tesla V100** despite that encoding pin. CUDA visibility alone does not select OpenGL browser hardware.
- After the Linux Vulkan binding, the browser probe reported **ANGLE / Vulkan / NVIDIA GeForce RTX 3060**. A real accelerated eight-second render passed source comparisons; reported hardware render duration was 14.9 seconds for that small test. This is not a long-video performance benchmark.
- The following second-recording subtitles export used GPU acceleration and passed its remote source-picture checks before the output-directory failure described above.
- The unapproved Windows test reported RTX 4050 for NVENC selection and D3D11 browser drawing and passed its short test; that result does not excuse launching it without permission.

Do not claim all hardware/vendors, all native packages or every clean environment are production accepted. Also do not re-encode completed files just to make a GPU claim. The first recording's two completed exports used the earlier CPU QA path; they were preserved until the later missing-file/download failure.

## Task helpers and evidence

Helpers under `scripts/lab/` include:

- `workflow_probe.py`: selected server/engine/job readiness; optional pairing.
- `recording_server_probe.py`, `inspect_recordings.py`.
- `recording_transcribe_worker.py`, `start_recording_transcription.py`: isolated remote transcription/runtime preparation.
- `recording_edit_worker.py`: earlier custom/manual preparation route; not the full pipeline runner.
- `recording_pipeline_worker.py`: actual `Pipeline.run()` plus export, GPU selection, source-picture checks and checkpoint manifest. Currently stopped; do not launch it.
- `start_recording_edits.py`: remote launch helper and isolated smoke options; no resume is authorized now.
- `deploy_recording_support.py`: backup/stage/deploy only selected files to the own server root, refuse active API jobs. Its standalone-worker guard was initially specific to `edit.py`; do not assume it covers every future worker name.
- `fetch_recording_progress.py`: status/transcript/output download helper. **Known direct-destination truncation bug remains; do not use it to overwrite valuable local files.**
- `preview_pipeline_motion.py`, `preview_recording_correction.py`, `check_recording_gpu.py`: QA helpers, including the mistaken local GPU test route. Do not infer authorization from the existence of a command/flag.
- `inspect_recording_run.py`, `stop_recording_work.py`, `inventory_stopped_outputs.py`: own-process/status/output inspection and stopping. The final stop helper targeted only QA roots in the own remote QA folder and their descendants, not engine services.

Evidence in `docs/evidence/` and `dist/recording-acceptance/`:

- `render-acceleration.xml`: latest focused selection, **32 passed, zero failures/errors**.
- `acceleration-client-build.log`: latest Studio production build passed.
- Earlier recording-only selection: 26 passing composition/caption/recording checks. These overlap the 32, so do not sum them.
- `recording-asr-fallback.xml`: three focused ASR fallback cases.
- `client/studio` timeline suite: **23 passed** at this checkpoint.
- `gpu-browser-render.log`, `render-smoke.json`, `render-status.json`, `render.log`, `edits.json`, transcript files and before/after/actual-output PNGs.
- Historical product boundary acceptance: 54 focused Python passes, 12 overlapping source/package checks, nine storage/caption/path checks and three additional containment checks. Native transport/companion/Director/bootstrap checks passed in those checkpoints.
- Historical larger regression reports exist; they predate later changes. Some earlier full runs recorded failures/errors. **No current full-suite, complete UI or production-ready certification is claimed.**

Do not run more checks merely to improve this document after the owner's documentation-only instruction.

## Deferred requests — all stopped, not authorized to resume

The prior order was recorded in `docs/ACTIVE-WORK.md`; its older “Active” wording is superseded by this stop notice.

1. Finish/recover the four recording variants and their editable projects. Current deliverability failure must be resolved first if the owner authorizes recovery. Do not silently recreate or delete data.
2. Add background music to a separate version of the original `2026-11-02 09-13-35.mp4`, preserving narration and keeping music low/ducked beneath speech. The stated assumption was original picture as the base; it was not started.
3. Research/document reliable window/UI-region/cursor-focus detection and keyframe algorithms. The owner requested **research, not implementation**. No cursor/window detector was installed or run. Primary-source research was collected but the report was not finished.
4. Premiere Pro export beta feasibility: plan/check only. Need verify interchange support for clips, cuts, captions, audio, graphics and keyframes; distinguish editable interchange from rendered layers. Not implemented.
5. Automated app-walkthrough video/harness plan, **no implementation**. Reference `https://github.com/tanbiralam/claude-code.git`; script/steps/narration/annotation manifest; timestamped voice; deterministic app actions; synced highlights/cursor/recording; music ducking/end card; localization. Verify the proposed workflow's claims and fit it to the client companion/remote processing architecture. Not yet planned fully.
6. Later experiment: full-screen motion-graphics cutaways during a visually stable narrated screen segment. Example: approximately eight seconds of talking with no meaningful scene change; retain the recording for the first three/four seconds, insert a relevant full-frame animated explanation, return in sync. Do not layer more text over already text-heavy pages. Investigate OpenCV stability evidence and available Claude/video skills. Distinguish important reading from inactivity; protect scrolling, clicks, typing and figures. The owner explicitly deferred this until the earlier work was done. No implementation was started.
7. Earlier app vision/backlog: full editor option/drag acceptance, measured Director/regeneration quality, all backend capabilities surfaced intelligibly, external skill gaps, Share/Shorts real acceptance, installers/clean environments/Linux CI/release and consolidation of stale documentation. Not completed by the focused tests above.

### Collected research pointers for the uncompleted detection report

The proposed direction is a hybrid, not a claim of a proven reliable detector: native pointer/window/accessibility telemetry for future recordings; screen/document-region parsing plus cursor detection/tracking and speech/OCR/event fusion for existing MP4s; confidence/abstention and full-frame fallback; protected figures/text; editable focus/keyframe provenance.

Primary references already consulted include Microsoft Desktop Duplication/UI Automation/DPI docs, XDG ScreenCast cursor metadata, Microsoft OmniParser, UIED, PP-DocLayout/PP-StructureV3, OpenCV masked template matching and optical flow, SAM 2, Google AutoFlip and the CVPR 2011 L1 camera-path paper. The app already has L1-style face camera smoothing; it does not thereby have cursor/window tracking.

Relevant cautions: cursor is not gaze or guaranteed intent; screenshot grounding metrics are not video-tracking accuracy; synthetic cursor results do not establish reliability on these recordings; dense dataset coordinates may include retained last-known hidden cursor positions. `ldenoue/cursor-motion-detector` was inspected as research but is PolyForm Noncommercial, not a freely shippable commercial dependency. No detector weights were downloaded. The future report must cite original sources and clearly separate published measurements from proposed architecture and unperformed validation.

## Cleanup inventory and preservation boundaries

The final inventory found root `.pytest_cache`, `.venv`, `.tools`, installed models/caches, projects, settings and source inputs; `dist/legacy-combined`; recording QA source samples/previews/local smoke copies; and native client/server installer artifacts. No comprehensive deletion/move pass was performed before “just document.”

If cleanup is later authorized, distinguish disposable build/renderer/pytest/bytecode caches from source, user data, model environments, installers, transcripts, evidence and outputs. Verify every recursive target resolves within the intended workspace before deletion. Do not delete the dirty/untracked `client/` and `server/` product code. Do not remove `.git`, `.env`, settings, credentials, model environments, original recordings or user projects merely because they look untracked. The zero-byte MP4s must never be presented as working videos.

This file is the authoritative stop-state summary. Older success screenshots/logs are evidence of what was observed then, not proof that the corresponding deliverables or services are available now.

### 2026-11-04 additions (all uncommitted; see WORKLOG.md for detail)
- **Sound mix is user-controlled:** Options `music_volume` (default 0.10), `duck`, `duck_amount`, `duck_release`, `target_lufs`, `music_fade_in/out` flow
  schema -> `pipeline.export` -> `render/mux.py mix_and_mux`; UI = `components/MusicMix.tsx` (Automatic/Yours badges) in the editor Sound panel and Export page. Tests: `tests/test_music_mix.py`.
- **Server jobs:** `server/jobs.py` keeps a per-job log (`GET /api/jobs/{id}/log?after=N`); UI = `components/JobsPanel.tsx` on the Server page (Details button = full log).
- **Preview speed:** `review/Preview.tsx` `pace` ref skips frames/posts on slow machines. Not measured on a heavy project yet.
- **New video choices:** each choice is a tile (Auto/Yours) opening its own page of visual cards (`pages/NewOptions.tsx`, `new-options.css`). Dark-theme override keeps checked cards readable.
- **Director's script review:** `server/script_review_routes.py` + `pages/ScriptReview.tsx` (`/p/:id/script`); option `review_script`; answers need a connected Claude/Codex director (not tested live).
- **HyperFrames `check`** runs before every export (`render/hyperframes.py check`, `vt check <project>`, `GET /api/projects/{id}/script-review/render-check`). Unused HyperFrames commands: beats, audio, transcribe, catalog/add, compare, media-treatment, normalize-audio.
- **Icons:** client orange, server blue. Build the Windows client with `scripts/build_client_windows.sh <outdir>` (embeds the icon with rcedit; plain electron-builder leaves the default icon).
- **Still open:** re-run recording 2 with the new music default; silent uninstaller leaves program files; Windows *server* installer icon not rebuilt; heavy-timeline preview (hide off-playhead elements / low-res scrub).

- 2026-11-04 evening: explicit choices now win for recordings. Cause of "nothing applied": a screen recording is auto-set to "Keep my video" (recording_edit=subtitles), and New.tsx then forced music=null/sfx=false; the director is never asked in that mode (1 scene, planner=rules), and "Automatic" music was never resolved there (pipeline.stage_plan now resolves it first). screen_recording.layout keeps sfx cues in screen+graphics mode when sfx is on. Script page shows a "kept as recorded" card with POST script-review/add-graphics (switches to screen+graphics and re-plans). New video hub has a "What will happen" box. Server NOT redeployed yet (needs GPU_PASS).

## 2026-11-05 Cartoon 2 (story engine) + Cartoon 1 extras + everything editable
Plan and status: docs/STORY-ENGINE-PLAN.md. Engine source: server/renderer/story/src (rebuild with `node server/renderer/story/build.mjs`; React comes
from client/studio/node_modules). Python: server/vt/story/. Studio: client/studio/src/review/story/, review/JsonField.tsx; Vite/TS alias `@story`.
Tests: tests/test_story_engine.py (8). Do not edit runtime/vt-story.js by hand. Times inside stories are absolute video seconds.

## 2026-11-05 One director per video; the AI directs (owner's direction, read this first)
Owner: the AI dictates the video, no static rules on top, no mixing of models, every prompt and answer visible. What changed:
- `Pipeline.director()` picks one director; `Pipeline.run` makes it the provider for every stage. Claude/Codex on the person's computer: `AIP.NoProvider` on the server, so no local model touches understanding, voice direction or planning. Before this a Claude video also ran the local picture planner and a server script pass.
- Rule passes (`fix_hook`, `fix_numbers`, heartbeats, sound stickers, Cartoon 1 motif extras) run only on rule-made plans (`ai_directed` in `stage_plan`); `craft.check` still reports on AI plans. The first `apply_speaker` still runs for imported video, because the a-roll is never offered to planners.
- "Claude on the server" now really directs explainers (`script_service.uses_script`, `direct(want_ai=True)`); it used to return the rule plan credited to Claude.
- `vt/house_rules.py` is direction text only, appended to every director's brief. It rejects nothing. Add lessons there, not validators.
- `vt/ai/talk.py`: every prompt and answer goes to `ai_talk.jsonl` in the project (complete_json, llm.chat_json, broker, MCP tools); Studio: Details, AI conversations (`log/AiTalk.tsx`, `GET /api/projects/{id}/ai-talk`). Render-time vision checks run outside `Pipeline.run`, so they are not logged yet.
- Local AI context now grows with the prompt (`providers.context_for`): a fixed 16K context cut replies off mid-JSON.
- Progress: `_say` never goes backward; `_tick_progress` moves the bar while a stage waits (estimate from `STAGE_SECONDS`, stays under 95 %).
- New: audio + .srt (`ingest.attach_subtitles`, `vt new --srt`, MCP `srt_path`, New video page): skips speech recognition for every style; Cartoon 2 captions follow the SRT lines. ElevenLabs engine (`tts._synth_elevenlabs`, key in Settings, Voice & speech; not tested against the live API, no key here). Bensound tracks in the server's user-music (`scripts/lab/fetch_bensound.py`, credit kept, not bundled in installers). Character look picture cards (`components/PictureChoices.tsx`, `/api/elements/cartoon/preview?look=`).
- Fixes: ComfyUI Breeze device-split crash retried after `/free` (`comfy/voice.py`); speech model download shows real progress.
- Still static, for the owner to decide: `vt/script/story_kit.py` compiles Cartoon 1 into fixed sets; `vt/story/engine_rules.py` drafts Cartoon 2 before the AI designs scenes; Auto music picks by mood table (`musicpick.py`), not by the director.

## 2026-11-05 11:15 The director places things and sees its own frames
- Every element takes x, y, scale, rotation; every director's brief says so (`script/prompt.py PLACEMENT`, `planner/prompt.py`).
- Local AI and Claude on the server: `vt/director_review.py` runs at the end of `stage_compose`: one frame per scene goes to the plan's own director, its changes are applied, up to 2 rounds. Report: director_review.json. Claude's CLI sees frames with its Read tool (`ClaudeCLIProvider`, tested with a real image).
- Claude or Codex on the person's computer: the prompt tells it to use MCP `preview_frames` and `update_scene`. Tested with the exact `director-runner.js` command against the server (scratch: project 2026-11-05-look-local): about 40 images per run, faces clear, Maya consistent. Roughly 6 minutes and an estimated 3 dollars of Claude usage per video; two runs plus my session hit the owner's 5-hour limit once.
- Fixed from Claude's own report: `apply_story_kit` replaced a director's cartoon with a default actor (repair_script adds one; the kit now keeps a written cartoon); `craft.check` crashed every time (`HIDDEN` defined twice in craft.py).
- `autopilot_finish` runs under the video's director and logs to ai_talk.jsonl. With an outside director the post-render AI steps (frame check, title) have no AI on the server.
- Limit found: gemma4 reads a sticker over a face as "visible" even when asked face by face. Local AI cuts stay weak; a better vision model is the way, not a rule.
- Open, from Claude: frame 0 shows only the set, because the character fades in and `entrance: none` does not stop it; characters in one scene arrive one after another; no riding pose; `get_current_script` stays the original draft after update_scene, so recompiling the script loses timeline fixes; craft.check skips 22 rules. Earlier "sweetsanymore" quote text not reproduced in Claude's cut, cause not found.
- Tests: 4 fail, none in code touched today: test_motion (server/third_party missing), test_restore_comfy_models (assets path), test_product_split (client/desktop/package.json extra icon entry), test_untested_four (doctor has no "Studio build" check). test_recordings_are_byte_identical failed on project.json before and after this work, cause not found; it runs speech recognition on the Windows PC, so leave it out of runs there (-k "not recordings_are_byte").

## 2026-11-05 16:10 What the frames taught: renderer, repair, measurements, UI
Owner: test with Claude on Sonnet (usage does not matter), then gemma. ElevenLabs waits. "In UI everything should look beautiful."
- Opening frame: `entrance: none` only removed the extra motion; `settleEntrance` in vt.js now puts every fade-in at its finished state, keeps long moves in time (the old skip-ahead put lips 0.7 s ahead), and leaves a moment the director chose (`data: "chosen"`).
- Cartoon cast: `arrive` (seconds after the cartoon, 0 is there) and `y` (feet). Feet floated above the floor on 9:16: floor raised with viewBox 0 105, actors at bottom 31%. Per-scene `caption.y`, with a slider in Details. A word-reveal caption box fits the words said so far.
- "sweetsanymore" root cause: GSAP `_parseTransform` lifts a word out of a hidden scene and reinserts it before nextElementSibling, past loose spaces. `split` in vt-motion.js keeps each space inside its word.
- Coin: the twemoji 1fa99 art has a bank on it; replaced with a plain star coin (design/icons/emoji/1fa99.svg; deploy script now sends it and renderer/scripts).
- `frame_facts` (renderer/scripts/frame-facts.mjs, render/hyperframes.py, MCP tool): what covers which face or body, what is outside the frame, what overlaps, where the frame is empty, measured on the real page. Facts for the director; code changes nothing. Goes into director_review prompts and the laptop director's brief.
- Silent overrides removed: `submit_script` is strict (an overlay repair would drop comes back as an error with the reason; `apply_script(strict=True)`); a scene written with no actions no longer gets repair's default actor as a 3D teacher (`apply_story_kit`). One refused review change costs only its own scene (it used to discard every scene's fixes).
- `cartoon_choices()` gives every director the exact who, pose, expression and set values from the schema (Sonnet guessed `idle`, `run`, `shop_inside`, used `elder` for a mother).
- craft: pacing.dwell, pacing.read_time, captions.safe are measured now (feedback only); 19 still unmeasured. `world: "3d"` no longer reads as the number 3. "two hundred and fifty" is 250 (`planner/rules.py`), which made Claude show "$200 and $50".
- `get_current_script` adds `edits_since_this_script` (video_script.plan.json is what the script compiled to). `submit_script` ignores that key.
- Server page no longer says Video Tool uses a card just because Ollama or ComfyUI holds memory on it. Ollama did hold about 1.17 GB on the V100 at one moment; it is the owner's service and was not changed.
- UI: seamless magic gradient, sidebar system numbers in one row, JSON tab fits, viewer test as a short list, built-in theme notice, selects visible, Export wraps on phones and has no black bars, editor header fits 400 px, phone tabs use the sidebar's names, thumbnails never block the result page and are not queued twice, a finished video's progress URL goes to its result.
- Not done on purpose: `guardLayout` in vt.js still hides overlapping elements in plans not edited by hand, which overrides a director; left for the owner to decide.
- Results: Claude Sonnet about 2 to 3 minutes per video, faces clear by frame_facts, real locations. gemma4 still makes weak picture choices (a car for "coin", a rocket for "shop") and leaves a quote over faces even when told; its creative quality is the limit.
- Tests run on the GPU server: scratch `server_tests.py` copies the code to /home/roy/vt-tests (own folder, own pydeps) and uses the RTX 3060. Never the Windows PC.

## 2026-11-05 17:00 The plan to carry out next
`docs/plans/PLAN-PERFECT.MD` is the owner's requested step-by-step plan for Sonnet (phases A to I, gates in its section 2, the owner's open decisions in its section 3). Progress is its tick boxes. Its test bench is `scripts/lab/vt_lab.py` (make, direct, export, sheet, frames, facts, report, tests); earlier scratch scripts are gone with their session. Correction to an earlier note: the desktop app can be started from a shell once `ELECTRON_RUN_AS_NODE` is removed from the environment; plan step H1 does this. Also: the desktop app passes no `--model` to Claude today, so it uses the person's Claude default; every "Sonnet" result so far came from `vt_lab.py direct --model sonnet`, not from the app (plan step B8).

Test baseline for that plan, on the server, 2026-11-05: 13 failed, 1303 passed, 12 skipped, 9 errors. Most come from one test leaking a fake Chrome path; causes are listed in the plan's step A4. This replaces the earlier note that only 4 tests fail: that run did not include everything that fails on the server. `test_recordings_are_byte_identical` still fails on `project.json`, cause not found (step A5).

## 2026-11-05 evening: the owner's decisions, now in the plan
`docs/plans/PLAN-PERFECT.MD` gained two phases, done straight after Phase A. Nothing is implemented yet.
- **Phase M, the helper.** Owner: Claude and Codex are usually not on the server, so a small micro server is always bundled with the client. It runs by itself in Electron's Node mode, starts with the computer, stays when the app closes, and calls out to the server's `/ws`. It adds an `ask` job, so every AI step of a video goes to the person's director through a new `ClientProvider`, and `NoProvider` goes away.
- **Phase K, graphics cards.** Owner: "v100 is for training. i should be able to select gpu while setup for multi gpu installations or servers." A saved list of allowed cards, enforced everywhere, asked in every setup. On this server Video Tool runs its own Ollama copy pinned to the RTX 3060, and the owner's Ollama service is not changed. **Until K6 is done, make no videos with the local AI**, because they can land on the V100.
- **Overlaps, decided.** Code never hides, shrinks or drops what any AI placed. Layout fits things, what still overlaps is measured and told to the director, and what is left is listed in the Quality check. Only plans made by the built-in rules keep the old guard (steps B2, B3).
- The owner agreed: "Style" and "Look", "Cartoon" and "Story cartoon", Sonnet as the default Claude model.

## 2026-11-06 Phases M and K are done (what works, what is parked)
Read `docs/plans/PLAN-PERFECT.MD` (ticks and Evidence lines), then `docs/evidence/perfect/BREAKING.md`: **everything that is broken, blocked or risky is listed there, on the owner's instruction ("list all the breaking stuff and finish rest of the implementation and then come back to it later").** Add to it when you park something.
- **Decisions since the plan was written (plan section 3):** 7, no key pairing: a computer on the server's own network connects with its address alone, anything from outside that network or forwarded still needs the server key. 8, the interface is **English only**; Bangla is a language for videos only (`tests/test_no_bangla_ui.py` guards it).
- **Phase M, the helper (M1-M6, M8 done; M7, M9 half, M10 open).** `client/desktop/helper.js` is a small always-on Node program (runs under the app's own exe in Node mode, one per user, calls out to each saved server's `/ws`, never listens for the network). The server sends it `direct` (a planning session over MCP) and `ask` (one question as JSON, pictures allowed). Every AI step of a video goes to the director that video chose (`ClientProvider`, `directing(project)`). Claude runs with `--tools ""` and only this server's MCP tools (the old flags allowed shell and file reads). A task survives a dropped connection for 90 s and is resent. The Settings, Directors page has a Helper card; the Server page lists the computers. The test bench runs the same helper: `vt_lab.py helper start|status|stop` (name "<this PC> (lab)"; leaves a remembered "Not connected" computer on the owner's Server page for 60 days).
- **Phase K, graphics cards (K1-K5 done, K6 done except its last check).** `server/vt/gpuassign.py`: the person's list of allowed cards (a saved `gpu.allowed`; none saved + two cards = one card only, the freest of those nobody else works on; a card already picked before the question existed counts as the answer), `apply()` fences the server (`CUDA_VISIBLE_DEVICES`) at `vt server`/`vt studio`/`vt engine run`, jobs `render`, `speech`, `ai` (Video Tool's own Ollama) and `pictures` (its own ComfyUI) with restart on change (`gpuassign.change`, one function behind the Server page, `vt gpu`, MCP), `engines/where.py` says in plain words where an engine that was already running sits and offers Video Tool's own copy. Asked in the Studio's Server page and setup wizard, the server's own pages (`/`, `/manage`), both server windows, `vt gpu setup` (install scripts, Docker `VT_GPUS`), `vt server --gpus`. **On the owner's server** (done and checked 2026-11-06): only the RTX 3060 is allowed; Video Tool's own Ollama runs on port 11444 pinned to it with its own folders and home; `gemma4:latest` is pulled there; the owner's Ollama service and ComfyUI (on the RTX 3060, not the V100 as an old note said) were not touched. See `K6-the-owners-server.md`.
- **Test habits that mattered:** a fake `nvidia-smi` on the path (`tests/test_gpu_setup.py`) found an infinite-ish loop in the card readings (534 calls); `tests/conftest.py` makes every test see a computer with no NVIDIA card and no remembered readings unless it gives its own; run card tests locally with `cd server && ../.venv/Scripts/python.exe -m pytest -c /dev/null --rootdir=.. ../tests/<file>` and leave `tests/test_gpu.py` off this PC (it uses the card).
- **Do not render on the owner's server** until they answer the question in `docs/evidence/perfect/A3-server-restarts.md` (it stopped hard twice on 2026-11-05 during render-heavy test runs). Reading, deploying code, one-file CPU tests are fine. Read `uptime` before and after anything heavy.
- **Nothing is committed.** Commit only when the owner asks, with no attribution lines.
