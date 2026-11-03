# Handoff for Codex (and any other agent)

The owner works with Claude Code and Codex interchangeably. Read this file first, then the tail of `WORKLOG.md` (newest entries at the
bottom) for details of what was done. When you stop, update both: what you did, what you verified, what is left.

## Latest continuation — 2026-11-03

**Current hardware authorization: remote GPU server `192.168.123.47` only. GPU-by-default production behavior does not authorize running the client PC GPU. Do not run local GPU workloads/tests without explicit permission. One eight-second local RTX 4050 test was mistakenly run and has exited; owner explicitly corrected this.**

**Current queue: [docs/ACTIVE-WORK.md](docs/ACTIVE-WORK.md). Finish the recordings before switching tasks.** Client dev UI is now `http://127.0.0.1:5173` connected to independent `.47:8790`; older :8878 notes below are historical. First recording's corrected subtitles and baseline text-motion MP4s are exported and decoded/visually inspected in `dist/recording-acceptance/exports`. Second recording's two versions remain in progress; a separate music version is queued afterward. The later full-screen motion-cutaway experiment is explicitly deferred.

**Owner requirements: preserve the original 1920×1080 canvas and ordinary overlay captions; do not invent an added caption band. Use available GPU acceleration, including in production QA.** Earlier QA forced CPU and was corrected. Normal export defaults were already GPU-on; UI acceleration is now automatic, with fallback progress and a saved acceleration report. NVIDIA selection tests actual encoding, respects CUDA selection, and pins Linux browser drawing through Vulkan to the same card. On `.47`, RTX 3060 NVENC and browser Vulkan/RTX 3060 passed a real eight-second source-frame test. The initial hardware probe picked V100 for browser drawing; it ended and the device-selection bug was fixed. Do not claim that initial probe used only RTX. Existing ComfyUI/Ollama and unrelated training services were not restarted.

See [recording export correction](docs/evidence/recording-export-correction.md): the real video factory must be visible to HyperFrames' inline-script media detection, or known-duration exports skip video extraction and freeze frame zero despite working snapshots. Failed output was quarantined. Current validation: 32 focused Python checks, 23 timeline checks and Studio build passed. Remaining jobs use `scripts/lab/start_recording_edits.py --full-pipeline`; status/downloads use `scripts/lab/fetch_recording_progress.py`. The old custom preparation runner is not an end-to-end pipeline test. SSH credentials remain transient environment values.

Fresh remote server installed per explicit owner request: [home-server notes](docs/ops/home-server-2026-11-03.md). UI http://192.168.123.47:8790, home-only `/home/roy/ultimate-video-tool-server`, own user service enabled/active at login. Existing ComfyUI/Ollama reused without changing their installs/services. Private Python CPU env and private Node/renderer installed; zero user projects imported. Real Breeze voice, Klein image, rendered frame and 1080×1920 H.264/AAC export passed; frame inspected. New Video default is Best available voice with plain-language provider/model labels; actual ready engine is resolved and recorded, Director voice modules share the policy. Scene defaults follow it too. 28 + 19 focused tests pass; final voice/Direction check and Studio build pass. Test video and JSON evidence in docs/evidence/server-install. Linger=no, so automatic startup is at login, not promised before login. No credentials stored. User chose existing ComfyUI, so no second ComfyUI was installed.

**Latest visual follow-up: browser access is restored.** IAB works; local test Studio restarted on :8878, launcher 35572. Tested the disposable copy: Direction draft retention; picture/voice controls; live RUN → SPRINT and Escape restoration; Video settings returns to caption details; animated Typewriter preview; template insertion, Slide animation points and two undos restoring the original scene. Inspected desktop 1440×900 and mobile 400×760. Compacted tool navigation and Direction tabs after observing excessive header height; latest production build passes. Share selection works for an unexported video, Accounts onboarding and Shorts source screens inspected. Old browser-blocked notes below are historical. Remaining gates: full options/drag acceptance, actual scene regeneration quality, installers/Linux CI/release. IAB test tab marked for continuation; viewport reset.

Newest checkpoint: read [skills and Direction audit](docs/AUDIT-SKILLS-DIRECTION-2026-11-03.md) before older status below. Shared motion keyframes/templates, reusable story controls, Share/Shorts redesign and Direction panel are implemented in the working tree. Direction exposes per-scene instructions, actual recorded provenance, picture/video model choices and voice regeneration. Voice replacement preserves the exact cut clock, scene timing and anchored components; shorter narration retains hidden word anchors; one undo restores voice/mutes/captions. Generation guards preserve intervening scene edits. Direction drafts/jobs survive tool switches within the current app session.

Follow-up rendering is complete: direction-render/contact-sheet.png was inspected and shows updated “Run every day.” in all three formats; undo restores original data exactly. Docs checker passes. Live :8878 Direction endpoint works on the disposable copy. A final regression covers narration following moved scene boundaries instead of stale beat ownership. See direction-timing.xml for its result.

Latest checks: broad pre-Direction non-slow checkpoint 1,172 passed / 4 skipped; latest focused Direction/voice/motion/words/pipeline selection 33 passed, Studio build and 19 Node checks pass. Real story (9 frames) and motion (18 measured frames) checks passed earlier. Cua still reports local browser use disabled; do not claim fresh interactive acceptance. New caption-render check is scripts/qa_direction.py; inspect its log/result/contact sheet before claiming that pass. Installer files predate these changes; rebuild/reinstall and Linux CI/release remain outstanding. Preserve user uploads and existing working-tree edits. No commits/pushes this round.

Read docs/AUDIT-2026-11-03.md for the current vision-to-product audit and docs/evidence/capability-inventory.json for all 165 modules / 40 components. Older task statuses below and in the October docs are historical.

- Implemented unrestricted visual timing: exact scene edges/splits, independent element/action/caption ranges and transforms, stable action indices, caption undo, sound extraction, renderer library examples, opaque dropdowns, working Video settings toggle, responsive one-editor layout. Removed five-visual/six-sound truncation. Manual visuals survive automatic people-avoidance and scene splits retain actions once.
- Connected Director capabilities: complete discovery/schemas (formerly truncated), recent described-tool working set, shared exact edits through timeline.edit_scene, canonical graphics through timeline.place with all-format recomposition and no partial saves on unsupported content. English catalogue examples are shared with the library.
- Studio AI → All video tools exposes the live registry as searchable categories and labeled forms; shared CLI/MCP/API contracts remain authoritative. New exposes existing caption presets and optional reel closing line. Settings no longer claims a merely configured GPU address is connected or overwrites unrelated settings from a stale snapshot.
- Verified: initial 41 passed + 1 optional skip; expanded integration 113 passed; final follow-up 69 passed; Studio build, 17 Node behavior tests, desktop Director runner and docs checker pass. Live :8878 QA on the disposable -copy project verifies exact split 2.137s, removal 0.500s, mute/gain, undo/redo and layers in all formats; baseline restored. The user's original remains untouched.
- Real renderer frames in docs/evidence/free-editor-render and editor-actor-render verify visual timing beyond the original scene. Fresh Cua checks now pass: settings returns to selection; renderer example visible; caption draft RUN → SPRINT immediately, Escape restores RUN; free scene boundary drag saved 1.879s, Undo restored 1.600s; opaque dropdown; desktop, 960px window, 400×664 emulation and mobile tool browser inspected. Original project untouched, disposable-copy baseline restored. Caption editing was moved into Details so the canvas stays visible; transcript typing is live too. Tab switching resets scroll; mobile time input no longer shrinks. Normal desktop restored.
- Studio restarted on :8878, launcher PID 34584; live exact-edit QA passes again. Broad non-slow regression finished: 1142 passed, 4 skipped, 3 stale assertions (old 39 count / five-element cap) failed; all corrected assertions pass focused reruns. Additional 15-case follow-up passes. Full regression session 26011 remains running (docs/evidence/app-audit-full-tests.log, Python child 33896); last reported 65%, with failures to inspect when it completes. Do not claim full-suite green. Final correction selection completed: 48 passed (audit-final-corrections.xml), using an explicit workspace temp directory after default pytest temp setup stalled. Old full run: 1195 tests, 14 failures, 9 errors, 7 skips. All recorded honestly in audit.
- Follow-up correctness: fill.graphic now respects the requested slot instead of copied manual timestamps; language detection failure falls back to English; generic tool detail fields can create numbers, toggles, groups and lists. Studio build and 17 Node tests pass after the caption-panel changes.
- Open product gates are listed explicitly in the audit: universal per-sentence re-voicing with one undo; classic plan review; measured Director/Shorts quality; reference consistency; clean-machine packaging; live social account acceptance. No remote service modifications, posts, commits or pushes.

## The product in one paragraph

Video Tool turns a typed script, a voice recording or a link into a faceless short video. Retention is the metric: every change should make
people watch longer. The parts:
- `server/vt/`: Python package (FastAPI server, pipeline, director, renderer driver, MCP).
- `server/renderer/`: HyperFrames HTML/GSAP compositions rendered by Chrome.
- `client/studio/`: React web UI, served by the server.
- `client/desktop/`: Electron shell.

Engines: Ollama (the local AI), ComfyUI (pictures, clips, some voices), Edge TTS / other voices.

## The owner's standing rules (do not break)

1. **UI wraps everything.** Users never run commands after install. Every capability is one function in `server/vt/`, exposed as an `/api`
   route for the Studio, a `vt` CLI command, and, where useful, an MCP tool or module. Never ship a CLI-only feature.
2. **Never install into global Python.** Use `.venv` and `.tools/uv.exe` (Windows) / `.tools/uv` (Linux).
3. **Windows and Linux** now, macOS later.
4. **Never invent facts** (numbers, quotes, people). Scripts use only facts given or sourced.
5. **No commits, no pushes** until the owner asks again. The owner re-initialised git: `main` has only the README commit, and **all the
   work is uncommitted in the working tree. Do not reset, clean or stash it.** Never add Co-Authored-By or any attribution lines.
6. Connecting Claude/Codex is one click in the app, also when Claude runs on a different computer from the server.
7. Apple design principles; the design-auditor skill is at `C:\Users\Roy\design-auditor\SKILL.md`.
8. Decide, don't ask, unless it touches the owner's own systems or services (then ask, and give them the exact commands).
9. **English only for now.** Bangla is paused (it is in a bad state); lab runs use English cases; defaults are English everywhere.
10. **Teach the director, not one-off edits.** When a picture or a script is wrong, fix the rule or the prompt that made it, then re-run.

## Environment

**This PC (Windows):**
- Repo: `C:\Users\Roy\Desktop\ultimate-video-tool`.
- Python: `.venv\Scripts\python.exe` (3.11). Sync: `.tools\uv.exe sync --extra dev --extra cu124`.
- `ffmpeg` and `node` are not on PATH by default. Add
  `C:\Users\Roy\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin` and
  `C:\Program Files\nodejs`.
- Tests: `.venv\Scripts\python.exe -m pytest -q -p no:warnings tests/`. Run long selections in the background: a full run takes over
  10 minutes.
- Studio: `cd studio && npx tsc --noEmit`, then `npm run build`.

**The lab Studio** (what the test rounds use):
`VT_PROJECTS='C:\Users\Roy\Videos\Video Tool Lab\story\projects' HYPERFRAMES_NO_TELEMETRY=1 .venv/Scripts/python.exe -m vt.cli studio --port 8771 --no-open`,
with ffmpeg and node on PATH.
- It must be restarted after any Python change.
- **Before restarting, stop every old one.** Stale processes kept serving old code twice today. In PowerShell:
  `Get-CimInstance Win32_Process -Filter "name='python.exe'" | ? { $_.CommandLine -match 'studio --port 8771' } | % { Stop-Process -Id $_.ProcessId -Force }`

**The GPU server:** `roy@192.168.123.47`, Ubuntu, Tesla V100 16 GB (GPU 0) + RTX 3060 12 GB (GPU 1).
- `scripts/lab/rs.py "<cmd>"` runs a command there and `scripts/lab/put.py <local> <remote>` uploads a file. Both take the password from
  the `GPU_PASS` environment variable (the owner gave it: ask them). From Git Bash, set `MSYS_NO_PATHCONV=1`.

**Services on the server:**

| Service | Where it runs | Do |
|---|---|---|
| **ComfyUI 8188** (`comfyui.service`) | the RTX 3060 (`CUDA_VISIBLE_DEVICES=1` in its override; backup `override.conf.bak-v100`) | It is the owner's install, published as `comfy.atanusroy.com` through Cloudflare. Use it; **never change its install or service yourself**: give the owner the commands. It reads models first from the SSD `/run/media/roy/OPT/comfyui-models` (section `fast_ssd` in `/mnt/bigdata/video-tool/comfyui/extra_model_paths.yaml`, backup `.bak-before-ssd`; fstab entry by UUID, `nofail`), then from the HDD. |
| ComfyUI 8189 (`comfyui-audio.service`) | — | stopped and disabled at the owner's request |
| **Ollama 11434** | pinned to the 3060 | `CUDA_VISIBLE_DEVICES=<3060 UUID>`, `OLLAMA_SCHED_SPREAD=0`, `OLLAMA_LLM_LIBRARY=cuda_v12`. Its Vulkan backend ignored the CUDA pin and used the V100. Backup `override.conf.bak-two-gpus`. It also serves the owner's chat site. |
| The V100 | — | the owner's (ML training). Do not put our work there. |

- ComfyUI and Ollama **share the 3060 and take turns**: `llm.release()` unloads the AI before pictures, `llm.make_room()` unloads
  ComfyUI before the AI.
- Our server install: `/mnt/bigdata/video-tool-server/app` (a copy of `server/vt/`; sync with a tarball through `put.py`). Never touch
  `/mnt/bigdata/video-tool` except the model folders.

**This PC's settings:** Ollama `http://192.168.123.47:11434`, ComfyUI `http://192.168.123.47:8188`, `picture_recipe=klein-4b`.

## Where things are

| Area | Files |
|---|---|
| Client/server, pairing, MCP bridge | `docs/plans/PLAN-CLIENT-SERVER.MD`, `server/vt/server/serve.py`, `server/vt/server/clients.py`, `server/vt/server/discovery.py`, `client/desktop/` |
| Find/choose a ComfyUI, VRAM fit, picture sets | `server/vt/engines/discover.py`, `fit.py`, `prepare.py`; `vt engine find / use`; Studio `components/FindEngines.tsx`; `/api/discover` |
| Picture graphs | `server/assets/comfy/workflows/klein_t2i.json` (default), `qwen21_t2i.json`, `zimage_t2i.json`; `server/vt/comfy/workflows.py picture_workflow()` |
| Reel director (pictures per moment) | `server/vt/reel/reading.py` (the local AI director's prompt), `server/vt/reel/plan.py`, `server/vt/reel/style.py` (`prompt_for`, `cast_for`) |
| Plan document (places, cast, moments) | `server/vt/direction/plan_doc.py` (ops `set_place`, `set_moment_place`, `set_cast`, `set_prompt`, `merge`, `set_medium`, …) |
| Craft rules and checks | `server/vt/craft.py`: areas `script`, `hook`, `sync` (`picture.place`, `picture.drawable`), `pacing`, `captions`… |
| Hand-back (text leaves the picture) | `server/vt/compose/composer.py` (`until`, `_hand_cards_back`), `server/renderer/runtime/vt.js`, `vt-media.js`; `tests/test_handback.py` |
| Lab scripts | `scripts/lab/` (`draw_render.py`, `bench_models.py`, `director_run.py`, `claude_direct_billionaire.py`, `places_lamp.py`, patch_*.py history) |
| Lab outputs | `C:\Users\Roy\Videos\Video Tool Lab\` (`story/one-gpu/` has the videos judged on 2026-11-01) |

## What the owner wants videos to be like

The model is `samples/scripts/billionaire-tax-easy.txt`, the owner's "Why Do Billionaires Pay Less Tax Than You?" made easy:
- the title spoken first;
- two named characters (an everyday person and a contrast);
- a question chain, where each part ends on the viewer's next question;
- toy round numbers, then real facts;
- one takeaway line per part, shown as a full-frame card that hands the frame back;
- **very easy words.**

Pictures: every prompt is self-contained, because each picture is made alone. Each one names:
- **the place**, with the size of things in it;
- **the people**, with their looks;
- **only what is visible:** no "not", no similes, no objects that carry writing.

For rare poses, use a close-up of the telling detail. Craft areas `script` and `picture.*` measure most of this.

Best result so far: `story/one-gpu/billionaire-claude-v2.mp4`, Claude as director with FLUX.2 Klein on the 3060. Compare it with
`billionaire-local-ai.mp4`: the local AI is the weaker director.

## How to work: every task, start to finish

The owner wants each task finished properly, not started. Work through the list below **in order**, and take each task through all these
steps before the next. Do not stop halfway to ask; the only questions are about the owner's own systems (see rule 8).

1. **Understand.** Read the task, the plan file it names, and the code it touches. Write a short plan in WORKLOG.md: what you will
   change, how you will know it works.
2. **Build it everywhere it belongs.** One function in `server/vt/`, then:
   - an `/api` route;
   - the Studio UI (a screen or control a person can use, typechecked and built);
   - a `vt` CLI command;
   - an MCP tool where an assistant would use it.

   A feature that only exists in Python is not done.
3. **Test it.**
   - Unit tests for the logic and the edge cases (`tests/`, real files, not mocks of our own code).
   - The related existing tests.
   - A full `pytest` in the background before you call the task done.
   - Fix every failure you caused.
4. **Run it for real.** Restart the lab Studio (stop the old ones first). Make a real video through it on the GPU server (pictures on the
   RTX 3060), the way a person would. For UI work, drive the Studio with Playwright and look at screenshots.
5. **Look and listen.**
   - Make a contact sheet of every video: `scripts/lab/draw_render.py` makes one, or call `video_lab.strip(video, out_png, times)` from
     `scripts/video_lab.py`.
   - Look at it. Listen to the voice. Read the craft check and the retention scorecard.
   - Write the judgement in WORKLOG.md: what works, what fails, and why.
6. **Fix the cause, then go again.** Every failure gets fixed where it comes from: the director's prompt, a craft rule, the composer, the
   renderer, a model setting. Not by hand-editing that one video. Re-run step 4 until the video is right or the remaining problem is a
   known model limit (write which).
7. **Finish.**
   - Update WORKLOG.md (what changed, files, what you verified, the video path).
   - Update this file: mark the task done, add new traps and anything left.
   - Then start the next task.

**Done means:**
- it works from the Studio, the CLI and MCP;
- the tests pass;
- a real video made with it was looked at and judged;
- the logs are updated.

Anything less is "in progress", and the next agent must be able to see exactly where you stopped. Never commit or push (rule 5).

## Tasks, in order

1. **Director choice (the owner's next ask).** Build `docs/plans/PLAN-DIRECTOR-CHOICE.MD`:
   - the registry of who can direct now (`GET /api/directors`);
   - the New-page and Settings choice, with a fallback order;
   - Claude on the client PC directing a remote server: the desktop app announces `claude` over `/ws`, the server sends a `direct` request,
     the client runs `claude -p` limited to Video Tool's MCP tools, and the server falls back to the local AI after a timeout.

   Test with a fake device, then for real on the billionaire script.
   - **Implementation and local live paths complete (Codex, 2026-11-02):** registry/API/project choice/Studio Settings+New+Review,
     CLI/MCP, Electron broker and constrained Claude runner are built. Local Electron uses stdio MCP; remote clients use revocable HTTP
     tokens. `get_reel_plan` / `check_reel_plan` expose self-contained prompts and picture checks. Focused tests, Electron allowlist/config
     tests, CLI/schema/compile checks, Studio typecheck/build, a complete Chrome Studio render with Claude on the server, and a complete
     Electron render with `Claude on This computer` all pass. The advanced editor visibly reports the saved director. The fresh Electron
     server had to download its recommended `gemma3:4b` model once before context analysis; this is setup time, not a director fallback.
     Still required for the repository's full “done” definition: finish/triage the long full-pytest run and the real billionaire GPU
     comparison/judgement (requires the owner's GPU credential). See WORKLOG for project IDs, visual findings, and the exact test boundary.
### Desktop flow redesign completed 2026-11-02

- No startup setup banner. The primary creation path is three steps: content → posting shape → create.
- Do not reintroduce an Advanced disclosure. The owner explicitly wants every useful choice visible, but described in ordinary language.
- The final create screen visibly lists all optional choices; Automatic remains the safe default for every technical decision.
- Settings shows a simple readiness/defaults card first and the complete settings list below, with labels such as “Where work runs,”
  “Who plans each scene,” “Make moving pictures,” and “AI helper on a computer.”
- For now both AI planning and picture generation use the remote GPU server at `192.168.123.47` (Ollama `:11434`, ComfyUI `:8188`).
- Electron visual QA and production build passed. Focused director tests pass using the repository `.venv` (6/6) and the desktop runner passes.

2. **Natural, expressive narration for every video (owner, 2026-11-02: "natural voice with tones and ups and downs").**

   Today English uses Edge TTS: clean but flat, because its free endpoint only changes speed. The parts for expression exist but are not
   on by default:
   - `server/vt/voice_direction.py`: per-sentence delivery notes `{...}` and sounds `(laugh)`; `suggest()` lets the director write notes.
   - Breeze TTS 2 on ComfyUI 8188 (`server/assets/comfy/workflows/breeze_direction.json`, `breeze_design.json`, verified on the 3060 on Oct 28).
   - The one-narrator lock (`server/vt/voice_lock.py`).

   Do:
   - **The director writes delivery notes from the script's structure:**
     - the title and questions: curious, rising;
     - numbers: punchy;
     - takeaway lines: slow, firm;
     - character lines in character.
   - **Breeze speaks with one designed narrator per video.**
   - **A measured flatness check:** pitch range and rate variation per sentence.
   - **A/B on the billionaire script:** Edge vs Breeze with notes, judged by ear and by the check. Make Breeze the English default if it
     wins.

   Breeze is about 3.5 s of compute per second of speech on the 3060 and shares the card with pictures (turns: release/make_room).
3. **Finish round 2 (hand-back).**
   - Add the measured check: an element covering more than 35 % of the frame for more than 3 s, or a picture covered for its whole moment.
   - When a word card is on screen, the caption under it repeats the same words ("BUY. BORROW. DIE." over "buy, borrow, die."). Hide the
     caption, or make the card replace it.
   - Verify on an explainer with stat and quote cards over pictures.
4. **Round 3, styles (English).** The billionaire script (Claude-directed plan, cast and places kept) in 8 contrasting film styles. Judge:
   style fidelity, cast consistency, caption legibility per palette, and the style text in `film_style_text`.
5. **Round 4, scripts (English).**
   - Write 5 new 60–120 s scripts in the owner's style (story, science explainer, how-to, top-5 list, opinion); run each with Claude
     directing. Each must pass the `script.*` checks.
   - Re-run the English lab cases: `scripts/video_lab.py --only explainer-general,story-cartoon,product,infographic,stick,emoji,mixed-wide`.
     The earlier round-03 run was stopped after its Bangla cases.
6. **Round 5, renderer (HyperFrames).**
   - Every element type (37) and layout (7) in 9:16, 16:9 and 1:1.
   - Motion presets and caption styles.
   - Overflow, cut-offs and render time.
7. **Round 6, engines on one card.**
   - Voices and the one-narrator lock.
   - Music: library vs ACE-Step.
   - Clips (Wan 2.2, LTX 2.3) as VRAM-fit sets like the picture sets.
   - A-roll and shorts from a long video.
8. **Round 7, setup and client/server.**
   - First install with no ComfyUI (install our own on its own port), one or several running (choose), remote and deep scans, the
     Cloudflare mark, a worker that went away.
   - The Studio panel through Playwright.
   - MCP from the owner's PC to the server.
9. **Round 8, the suite and leftovers.**
   - Full pytest. Music-catalogue regression repaired on 2026-11-02: preference/variety tests now use an isolated catalogue, with explicit fallback and real bundled-track checks (5/5 pass).
   - Remove the 64 `server/design/themes/auto-*` folders left by old projects.
   - The gemma4 context step (~150 s), post-plan QA time (~6 min), Studio timeline smoothness.
10. **Not before the owner says:** `docs/plans/PLAN-CLOUD-AI.MD` (OpenRouter key kept in the OS keychain, budget, cloud director/critic,
   collage promo video type). Plan only.

## Known problems and traps

**Editor workflow and precision repair (2026-11-02, current):** Implementation and automated verification completed; visual sign-off is pending because Windows is locked.
- Editor now opens without the app sidebar. Menu restores navigation; Editing tools / Selection details / Focus on video control workspace panels.
- Left tools have explicit tasks; right panel distinguishes voice selection, added clips, scenes and whole-video settings. Exact playhead and clip/voice range fields are available.
- Fixed final-pointer-position loss, wide trim-handle offsets, exact voice/layer splitting, trim source offsets/fade limits, locked-track edit paths, stale save/refetch overwrites and phantom layer undo steps.
- Scene structure follows sentences. Scene split now offers the actual sentence boundaries rather than silently choosing a nearby one. Scene-edge previews show the actual landing boundary.
- Local added-layer text/position/timing/opacity updates feed the preview before the save returns. Element saves flush when switching scenes. Captions can be opened by double-clicking a timeline word.
- Narrow layouts retain the timeline; preview controls wrap and the video fits short windows. Project navigation remounts editor state. Keyboard shortcuts respect dialogs and focused form fields.
- Studio build and `npm run test:timeline` pass (13 regressions, including delayed-save races and a drag released before any intermediate move event). Focused audio/layers/caption Python tests pass (one optional skip).
- `scripts/qa_editor_precision.py --project 2026-11-02-why-do-small-habits-matter-copy` passes against :8878: exact 2.137s split, 0.500s cut, mute/gain, undo/redo, plus layer text/trim/position/opacity in all three composition formats. Test restores the copy's baseline.
- Full pytest is running with output in `docs/evidence/editor-full-tests.log` and JUnit in `docs/evidence/editor-full-tests.xml` (Python 39644, launcher 36584, exec session 91004). Its first failure was frontend EXPECTED_API=6 vs backend API_VERSION=7; corrected to 7 and that regression passes separately. At 20:24 local, the full run remains in `test_recordings_are_byte_identical` (real ASR, pytest temp root pytest-114).
- Remaining non-slow tests finished separately: 375 passed, 1 failed, in 233s, recorded in `docs/evidence/editor-remaining-tests.log` / `.xml`. Sole failure was the previously documented music test's assumptions about optional installed tracks. Repaired with isolated preference/variety fixtures plus explicit fallback and bundled-track checks; all 5 music tests pass on rerun. This is not a claim that the entire slow suite passed.
- The actual editor UI remains unverified after these changes: Cua screenshots show the Windows lock screen; user was asked to unlock. Next visual check should use the disposable `...-copy`, reload the page for the new build, and exercise both side panels, focus mode, precise split/trim, Escape cancel, caption editing, layer controls and undo/redo. Do not claim this visual audit passed.

**Caption preview repair (2026-11-02):** The small-habits project's transcript contained `run` while its composition still contained `walk`.
`edit_word` saved the transcript but composition failed with `FileNotFoundError` for `auto-y-do-small-habits-matter`.
`Project.theme()` now keeps a project-local theme snapshot and recovers older projects from the theme embedded in existing composition data.
Composer uses that resolver. The local Studio on port 8878 was restarted with the fix and the saved correction was reapplied.
Verified through Chrome: edited the word to `walk`, then back to `run` in Captions, without refreshing; the paused video visibly shows **RUN EACH** at ~2.55s.
Both caption regressions passed, including missing-library recovery; latest Studio typecheck/build passes.
The broader UI audit/full suite is not certified complete; see the current editor verification entry above.

**Picture models:**
- **FLUX.2 Klein** sometimes draws a person twice in one picture, ignores "winding" for stairs, and cannot draw an upside-down bicycle.
  Frame those as close-ups of the detail.
- Garbled letters appear on anything that carries writing; `picture.drawable` flags it.

**The plan file:**
- A job that is cancelled while drawing writes its in-memory plan back, undoing edits made to `plan_doc.json` meanwhile.
- The app refuses plan edits during a run, so only scripts that edit the file directly hit this.
- Consider re-reading the plan before the job's last save.

**Editing files:**
- Python written through a bash heredoc turned regex `\b` into a literal backspace (chr 8) three times. Use the editor or a script file.
- Check with: `python -c "import pathlib;print([p for p in pathlib.Path('vt').rglob('*.py') if chr(8) in p.read_text(encoding='utf-8')])"`

**Voices and timing:**
- Script voices' word times drift. `fit_script_words` (`server/vt/stages/align.py`) puts typed words back on the speech; never let a typed word
  be dropped.
- Abbreviations ("Mr.") must not end sentences or caption lines: `ABBREV` in `server/vt/stages/words.py`.

**The local AI director (gemma4):** it still writes "a figure" in some shots. A cast fallback figure then appears and confuses the
story. Consider having the reel director refuse a shot without a named person when the plan has a cast.

## Client/server architecture correction — 2026-11-03 (latest)

The desktop always keeps its native Node loopback companion for local Claude/Codex. The selected processing server (local or remote) owns projects, engines, storage and rendering. Do not restore page-lifetime-only assistant registration or install the GPU stack merely to connect remotely. See docs/plans/PLAN-CLIENT-SERVER-2026-11-03.md and docs/evidence/client-server-acceptance.md for implementation/evidence/limits.

Remote /home/roy/ultimate-video-tool-server on :8790 has current backend and Studio; existing ComfyUI/Ollama were connected and the fitted Klein files/workflow verified in the UI without downloads. Setup is four steps with server identity, separate install/model roots and GPU choice. Existing engine storage is constrained to that engine's indexed/configured folders; a new arbitrary folder requires a managed copy. Real signed-in Codex MCP list_projects through the native companion passed; both Claude/Codex readiness registered.

Native Node tests and focused Python checkpoints pass; current Studio build and final Windows NSIS build pass. Installer is client/desktop/dist/Ultimate-Video-Tool-1.0.0-win-x64.exe, unsigned; SHA256 fdfcf3e7b19dec65b1b44e64a9d7352cabc1ab27bd2de93edc7842bd8e363eaa. A per-user upgrade smoke test and additional regression selection are underway at this checkpoint; inspect latest evidence before claiming those passed. No full clean GPU stack or Linux desktop installation accepted, no release/push. Preserve unrelated training, user projects and all existing uncommitted changes.

Final architecture acceptance: architecture-acceptance-final.xml reports 45 passed / 0 failed. All three native Node checks and docs checker pass. Windows installer upgrade exited 0, installed companion files verified. Previous connection choice preserved in connection-before-server-architecture.json; current desktop choice targets http://192.168.123.47:8790 as authorized. Installed app startup log confirms that target and its Studio window is enumerated. Native window inspection hit app approval timeout, so do not claim native visual acceptance; browser setup/connection/model readiness/final Done were visibly verified. No verification processes intentionally left running.

## Product directory split — latest, 2026-11-03

Owner explicitly rejected a workspace bundled with the server. This supersedes the combined server-edition architecture above. Physical roots are client/ (studio + desktop client/companion/protected UI proxy) and server/ (vt + renderer + design/assets + desktop server manager + packaging + pyproject/uv.lock). No root symlinks. Root pyproject is pytest configuration only; root .venv is retained as the existing test tool environment. User projects/data remain in their original locations; no storage ownership migration was inferred.

Client now loads its own built UI through a session-protected loopback transport, with isolated per-processing-server Electron cookie partitions; API/media/WebSockets go to the selected server. It ships only ws as a production dependency and no Python/server bootstrap/resources. Server API no longer has an editor SPA fallback. Its / and /manage are standalone management pages, and native managers use Engine settings, not Open workspace.

Remote .47 API now serves management only; old app/studio files were moved to a separate /home/roy legacy backup. Linux GTK manager remains a user-home app/tray control (Electron sandbox unavailable; no system security changes). Both Windows products have separate manifests/locks/builds; inspected client resources are app.asar + studio, inspected server resources are app.asar + app-src with no Studio. Final installers built (client ~82MB, server ~237MB); per-user upgrade smoke test is underway. Preserve old data.

Node transport, companion, Director runner, server ports/control/bootstrap tests pass. Developer scripts implemented with private Node/uv/Python, role selection, updates, isolated dev data, launchers and JSON readiness. Real isolated client-only install/update with spaces and preserved data passes, plus PS parse/check. Full clean Linux development installation not yet accepted. Backend tests and final docs/installer checks still underway; inspect product-split-final.xml/log and package logs. Local Vite :5173 is running client UI against .47; paired and visually confirmed projects + New flow. IAB server tab is management; local client tab is the separate editor. Do not claim every historical task/test or native UI audit is complete.

### Contained server controls — latest checkpoint

Owner requires Engine settings to stay inside the app. Removed external browser/log-editor launches from both native managers. Windows uses an internal loopback-only engine frame and internal log view with Back; Linux GPU server uses its existing GTK/WebKit 4.1 libraries in the same window, also with internal logs. Embedded content cannot access Electron native-control IPC. Linux manager update is deployed, with manager/WebKit process checks; only the isolated Video Tool user service was refreshed. Existing engines and training remain untouched.

Product acceptance now has 54 focused Python passes, 12 overlapping source/package guards and 9 storage/caption/path passes. Real isolated client developer install/update passes on Windows and Linux. Contained-manager Node tests run the actual UI-state code and verify Back navigation, internal logs/settings, no external browser and IPC boundary. Independent client/server Windows upgrades completed; latest containment server upgrade exited 0, installed internal engine/log views were inspected in app.asar and its API restarted successfully with the existing environment/data. See docs/evidence/product-split-acceptance.md for current evidence and limits. Native controls have not all been clicked visually; do not claim a full native UI audit or GitHub release.

Final Windows server build includes the embedding policy; installed /manage?embedded=1 returns 200 with frame-ancestors restricted to self/file/loopback. Native window enumerated (Ultimate Video Tool Server); accessibility/monitor capture failed, so no native screenshot/click-through accepted. Extra three boundary tests passed (contained-product-boundary.xml); process lingered after reporting and was stopped. Server API healthy at :8790, PID 33308 at this checkpoint. Final artifact hashes are in product-split-artifacts.json. Vite :5173 remains available for client review; preserve unrelated local Python training/dashboard and remote engine services.
