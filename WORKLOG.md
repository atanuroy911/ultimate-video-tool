# Work log

Newest first. Every agent (Claude Code, Codex) adds an entry when it stops: what it did, what it verified, what is left. Read
`CODEX-HANDOFF.md` first.

## 2026-11-02 (Codex) — director choice (implementation complete; local live paths verified)

**Plan:** Build the director registry and fallback selection as one shared `server/vt/` capability, expose it through `/api/directors`, project
creation, CLI, MCP, and the Studio New/Settings flows, then connect the desktop WebSocket client so a logged-in local Claude can answer a
remote server's directing request with Video Tool MCP tools only. Verify registry/selection, fake-device completion, timeout fallback, and
tool allowlisting with focused tests; then typecheck/build Studio, run the related suite and full pytest, restart the lab Studio, and make
and judge the billionaire comparison through the real UI and GPU path.

**Built:** `server/vt/directors.py` owns the live registry, fallback policy and targeted request broker; `/api/directors` and a revocable
desktop-director MCP token are exposed; project options and metadata record the requested/resolved director and fallback reason. Reel and
ordinary plan paths now honor client Claude, server Claude and local fallback. The Studio New flow has a director step, Settings has order
and timeout controls, Review shows attribution, CLI creation commands accept `--director` and `vt directors` lists availability, and the
MCP `project.create` input carries the same choice. Electron detects/login-checks Claude, announces over `/ws`, runs it with only
`mcp__video-tool__*`, streams logs and reports completion (`client/desktop/director-runner.js`). Local Electron uses the bundled Python stdio MCP;
a client attached to a remote server uses a revocable HTTP MCP token. MCP now exposes `get_reel_plan` and `check_reel_plan`, including full
self-contained picture prompts and actionable `picture.place` / `picture.drawable` issues. Reconnect races, failed sends, Claude process
launch on Windows, one-token-per-session behavior, provider failure fallback, and accurate rules attribution were also closed.

**Verified:** all 6 `tests/test_director_choice.py` tests pass (targeted completion, absence, reconnect race, send failure, prompt/tool names,
reel-plan MCP payload/checks, API registration). The existing non-ASGI plan tests reached 15 passes before the first TestClient test was
stopped. Electron syntax and `npm run test:director` pass, including both stdio/HTTP MCP definitions and the exact tool allowlist. Python
compiles; schema construction, CLI listing/help, `git diff --check`, and the backspace scan pass. Studio `npx tsc --noEmit` and `npm run
build` pass. A real Studio was started on port 8878 and the New page loaded visibly in Chrome.

**Live verification resumed at the owner's request:** rebuilt `client/studio/dist`, started the real Studio on port 8878, and drove the complete
New flow in Chrome. Project `2026-11-02-why-do-small-habits-matter` selected **Claude on the server**, completed all 15 stages, rendered an
8.48 s vertical video, and saved `director.requested = director.who = claude-server`. Settings visibly showed Local AI and server Claude
Ready; `/p/<id>/pro` visibly showed `Who directed this video: Claude on the server`. Frames were inspected at about 1 s, 5 s, and 7 s. The
visual story and scene transitions worked, but the viewer check correctly flagged five retention-risk moments and four captions that pass
too quickly (first at 1.8 s); that pacing problem belongs to the later retention/caption task, not director selection.

Installed the locked Electron packages, launched `npm run start:repo`, and drove a second real flow through the desktop app. Electron
visibly offered **Claude on This computer — Ready on this device**. Project `2026-11-02-a-small-habit-becomes-easier-when` selected it,
completed the WebSocket/stdin Claude handoff, saved `director.requested = director.who = claude@local-app` with `planner = claude`, and
rendered a 3.58 s vertical video. A fresh local Electron server first tried to download its missing recommended `gemma3:4b`; cancelling the
synthetic run cannot interrupt `llm.pull()` because that stream has no cancellation hook. After the one-time model setup/restart, the
client-Claude handoff and render completed. `npm run test:director` and the Studio production build pass. The full pytest run is executing
outside the sandbox (Windows socket tests now work there); it reached 48% with one failure marker and several expected skips at the time of
this update, so its final failure details still need to be recorded. The real billionaire GPU comparison still requires the owner's
`GPU_PASS`. The separately rerun documented baseline failure remains exactly
`tests/test_music_auto.py::test_mood_picks_a_fitting_track_stably`: sports selects `upbeat`, while the test expects `hiphop`. No commit or
push was made.

## 2026-11-01, later (Claude Code) — styles, remote Claude, GPU builds, timeline, lab round 2 + matrix

**Done and verified (committed on `client-server`):**
- **66 film styles from lemo-opuscar** (MIT): `scripts/import_lemo_styles.py` -> `server/design/styles/<slug>.json` (style bibles) +
  `server/design/themes/style-<slug>/theme.json` (palette from the bible or its poster, its typeface, WCAG contrast, `picture: line` for drawn looks).
  26 typefaces added (`server/renderer/scripts/build-fonts.mjs`). `server/vt/styles.py`, modules `style.list` / `style.get`, `vt styles`, `/api/styles`.
  Planning and script tasks now carry `craft_rules`, the chosen `style` bible and the current `craft_report`.
  Gallery: `scripts/style_gallery.py` -> `C:\Users\Roy\Videos\Video Tool Lab\styles-gallery\index.html` (3 frames per style).
- **Remote Claude**: MCP `prepare_upload` gives a curl / PowerShell line with a one-time ticket (`PUT /api/uploads/<id>/file?ticket=`);
  `create_project` / `add_media` take `upload:<id>`. Test in `tests/test_upload_resume.py`.
- **Every NVIDIA GPU**: `server/vt/gpu_detect.py` (cu128 RTX 50 / cu124 default / cu118 old drivers / cpu), torch builds are uv extras
  (`--extra cu124` etc., one `uv.lock`); setup.ps1 / setup.sh / desktop bootstrap pick it; `vt doctor` shows "GPU build". Local: cu124.
  **Sync command is now** `.tools\uv.exe sync --extra dev --extra cu124`.
- **Timeline**: `client/studio/e2e/perf_timeline.mjs` measures frame times + Chrome layout/script costs. Fixed: timeline rebuilt on every clock tick
  during playback (Review.tsx memo) and zoom glide 15 -> 5 renders (Timeline.tsx). Play median 33 -> 16.8 ms, zoom jank 36 -> 16 %
  (machine under load). Conclusion: the slowness was React re-rendering, not Electron/JS; Rust/Tauri would not have fixed it.
- Context AI: tolerant beat-id repair (gemma4 answers no longer discarded). Captions: phrase splitter. Craft check + hook fix.

**Running / next:** round 2 (`round-02\`, same 10 cases as round 1) then the 69-video covering matrix (`matrix\`, `video_lab.py --matrix`)
start automatically. Then: compare rounds (`video_lab.py --compare <r1> <r2>`), judge sheets, fix, re-run. Not yet done: Review page
craft checklist UI; style picker grouping in the New flow (66 styles now appear in the theme list); deploy to the GPU server again.

## 2026-11-01 (Claude Code) — retention lab, craft rules, reference skills

**Done and verified (all committed on `client-server`):**
- Video lab `scripts/video_lab.py`: 10 cases (explainer, Bangla script, two real recordings, cartoon story, product, infographic, stick,
  emoji, 16:9 debate). Round 1 in `C:\Users\Roy\Videos\Video Tool Lab\round-01\` (scores: infographic 48, mixed-wide 54, product 61,
  Bangla 63, stick 80, others 90-100; by eye the high scores were too kind).
- Retention scorecard: new *picture hold* (changes over 8 % of the screen, captions excluded) and *fill*; weights rebalanced.
- Heartbeat: where no safe picture fits, the spoken word in big type (never a wrong-sense picture); key-term filter fixed ("the" was a key term).
- Topic detection from the opening sentence (`terms.topic_terms`); a verb that only starts sentences is not a name ("Skip").
- Spoken compound numbers ("eighty four percent" = 84 %, was shown as 4 %): `server/vt/planner/rules.py`, `tests/test_spoken_numbers.py`.
- Captions: phrase splitter (2-3 words, max 4; never end on a function word; never split a number; no lone words; appear 0.06 s after the word).
- Craft rules module `server/vt/craft.py` (24 rules with sources, 10 measured), modules `craft.rules` / `craft.check`, pipeline writes `craft.json`
  and opens the hook on the topic (`fix_hook`). On round-1 plans the check scores infographic 0, product 42, explainer 55 and finds every
  invented figure.
- A note about the video ("The video describes ...") no longer becomes the opening title (`archetypes.b_title_card`, context schema).
- One-click assistants (Claude Code verified with the real CLI, locally and against the GPU server).

**In progress / next:** lemo-opuscar styles; craft module in MCP tools / CLI / API / Review page; remote media upload for remote Claude;
CUDA matrix; lab round 2 and the full combination run; timeline profiling.

## 2026-10-31 (Claude Code) — client/server CS1-CS6

See `docs/plans/PLAN-CLIENT-SERVER.MD` (Progress sections) and the git log from `a64f68a` to `e7ec5b0`.

## 2026-11-01 (Claude Code): one card, find any ComfyUI, VRAM fit

- Owner's direction: one GPU per server (a typical PC has one); use the owner's EXISTING ComfyUI (8188, V100, behind the Cloudflare
  tunnel comfy.atanusroy.com) for everything; the second ComfyUI (8189, comfyui-audio.service) was stopped and disabled at the owner's request.
- `server/vt/engines/fit.py`: the VRAM calculator (weights at run precision + working memory + CUDA share; RAM = parked models + a read buffer).
  Picture "recipes" for the same Z-Image graph: zimage-full (bf16, 24 GB+), zimage-fp8 (UNET weight_dtype fp8_e4m3fn + Comfy-Org
  qwen_3_4b_fp8_mixed: 12/16 GB), zimage-fp8-small-text (fp4_mixed text reader: low RAM), zimage-nvfp4 (RTX 50). A set is picked only with
  15 % headroom (COMFORT) unless nothing else fits; partial offload only as a last resort. Language model by card: gemma3 12b/4b/1b.
- `server/vt/engines/discover.py`: scan a host (usual ports, or every port with deep=True) for ComfyUI (/system_stats) and Ollama ("Ollama is
  running" at /: Open WebUI also answers /api/version). On the server itself: process folder, CUDA_VISIBLE_DEVICES, systemd unit, and
  Cloudflare tunnel ingress (marks "published at ...").
- `server/vt/engines/prepare.py`: plan/prepare/use: download the set's missing files into the instance's own folders (/internal/folder_paths),
  check the graph, save comfy_url + picture_recipe; dead workers dropped. Remote instance + missing files = "install Video Tool's server there".
- `picture_workflow()` (server/vt/comfy/workflows.py) writes the recipe's loaders into zimage_t2i; reachable() attaches it as client.workflow.
  zimage_t2i_12gb.json removed. `llm.release()` unloads Ollama before pictures; `llm.server_vram_gb()` sizes the model by the server's card.
- Downloads: `installers.fetch` takes a lock file (two writers corrupted one .part on the server and lost the file).
- API: GET /api/discover, GET|POST /api/discover/prepare. CLI: `vt engine find [host] [--deep]`, `vt engine use URL [--recipe] [--yes]`,
  and the first `vt server` asks which ComfyUI to use. Studio: Engines page, "Picture makers found" (components/FindEngines.tsx).
- Tests: tests/test_engine_fit.py. End-to-end script: scratchpad e2e_onegpu.py (results in Videos/Video Tool Lab/story/one-gpu).
- Per-picture unload bug: `relieve_memory()` ran before EVERY picture and, with the server's RAM held by another job, reloaded the 12 GB
  model each time (2-5 min a picture). Now once before the batch and on a retry only: 20 s a picture on the RTX 3060.
- The owner moved ComfyUI 8188 to the RTX 3060 (CUDA_VISIBLE_DEVICES=1 in its service override; backup override.conf.bak-v100).
- Self-contained prompts (owner: "each image is generated separately, the prompt must not rely on context"): plan `idea.places` and
  `idea.cast` + `moment.place`; ops set_place / set_moment_place / set_cast; prompt_for(draw, style, cast_for(draw, cast), place).
  Director prompt (server/vt/reel/reading.py SYSTEM) teaches it; craft rules picture.place + picture.drawable (measured: no place, no size beside
  something big, negations, similes). Found and fixed literal backspace characters (a mangled `\b`) in craft.py and director/archetypes.py.
- Model bench (scratchpad bench_models.py, 5 hard shots, 3060): Z-Image Turbo 8-bit 21 s/picture; FLUX.2 Klein 4B 9 s/picture, better
  rooms and weather; both 11.5 GB peak; neither draws an upside-down bicycle (hence "close-up of the telling detail"). Qwen-Image 2.1
  Turbo int8 next. Models on the server's SSD (/run/media/roy/OPT/comfyui-models, fstab entry by UUID, nofail; extra_model_paths.yaml
  section fast_ssd, backup .bak-before-ssd); the HDD (5400 rpm) made each first load 5 min.
- Planned (not built): docs/plans/PLAN-CLOUD-AI.MD: OpenRouter key set once and kept in the OS keychain (headless: 600 file), hard budget, cloud director/critic/voice roles with local fallback, and a "collage promo" video type. `.env` added to .gitignore (it held the OpenRouter key, unignored).
- Round 1 done: The Last Lamp with FLUX.2 Klein (places + cast + drawable prompts) → story/one-gpu/the-last-lamp-klein-v2.mp4 (63.6 s; 29
  pictures in 5.9 min). Close-ups now take the place's visible details as a soft background (the place name drew the lighthouse's outside);
  the 9:16 paper-fit picture is 68 % tall so a two-line caption clears it. Left: Mira drawn twice in s21, straight stairs for "winding".
- Picture sets klein-4b (default 12 GB+), klein-4b-fp8, qwen21-turbo, each with its own graph (server/assets/comfy/workflows/klein_t2i.json,
  qwen21_t2i.json); the headroom rule (COMFORT) is off at the owner's request.
- Round 2, hand-back: elements now have an end. Schema `until_word`; the composer sets `until` (until_word, else over a picture: the
  sentence's end held 1.5-3 s); vt.js animates the exit. A text-only card scene longer than its line in a video with pictures borrows the
  nearest picture, which fades in when the card leaves (`backdrop.from`, keeping the card's own ink). tests/test_handback.py (7, one renders).
- Owner's reference script ("Why Do Billionaires Pay Less Tax Than You?") → script rules (craft area `script`): title spoken first,
  easy words in short sentences, question chain (measured, `craft.script_problems`); two named characters, toy round numbers then real
  facts, one takeaway line per part (rules for the director). Owner: "the entire script should be easy". An easy version written to those
  rules: samples/scripts/billionaire-tax-easy.txt (314 words, ~2 min; only facts from the owner's script).
- English only for now (owner: Bangla paused). A script is always spoken in the language of its letters (`tts.match_script`, in
  Project.create_from_script: API, CLI, MCP); English defaults everywhere (an English script had been read by the Bangla voice).
- Ollama pinned to the RTX 3060 on the server: CUDA_VISIBLE_DEVICES=<3060 UUID>, OLLAMA_SCHED_SPREAD=0, OLLAMA_LLM_LIBRARY=cuda_v12 (its
  Vulkan backend ignored the CUDA pin and used the V100); backup override.conf.bak-two-gpus. `llm.make_room()` asks ComfyUI on the same
  computer to unload before the local AI answers when the card is nearly full (mirror of llm.release()).
- Sentences: "Mr. Rich" no longer splits (ABBREV in server/vt/stages/words.py, in both splits). Script voices: `fit_script_words` puts typed words
  whose voice timing drifted into a pause back on the speech ("2011." had been cut from the transcript and captions).
- Local director: returns a cast and places now (moments get their place); named people, no words in pictures in its prompt.
- Director comparison on the billionaire script: local AI (2026-11-01-billionaire-tax-local-ai) vs Claude (…-claude, directed through the plan
  ops by scripts/lab/claude_direct_billionaire.py), drawn on the 3060 → story/one-gpu/billionaire-*.mp4. Plan for choosing the director
  and for Claude on the client PC directing a remote server: docs/plans/PLAN-DIRECTOR-CHOICE.MD.
- Director comparison judged (story/one-gpu/billionaire-local-ai.mp4 vs billionaire-claude.mp4, 107 s each): Claude wins clearly. Same Jack
  and Mr. Rich in every frame, every frame carries its line, a BUY. BORROW. DIE. card. The local AI let a fallback figure take half the
  video, drew two Mr. Riches, and put garbled words on calendars and notebooks.
- Caption lines keep "Mr. Rich" together (composer _tidy_chunks uses words.ABBREV). Rule picture.drawable also flags objects that carry
  writing (newspaper, calendar, sign, screen, counter...) unless shown closed / from the side / far away; the director prompt says the same.
- WARNING for anyone editing: Python written through a bash heredoc turned regex `\b` into a literal backspace (chr 8) three times today
  (craft.py, director/archetypes.py). Check with: python -c "import pathlib;print([p for p in pathlib.Path('vt').rglob('*.py') if chr(8) in p.read_text(encoding='utf-8')])"
- 2026-11-02: CODEX-HANDOFF.md rewritten as the starting brief for Codex: current environment (8188 and Ollama on the 3060, models on the SSD,
  no commits, English only), what the owner wants videos to be like, tasks 1-9 in order (director choice first), known problems and traps.
- 2026-11-02 caption mismatch investigation and verification: trace the saved transcript through composition and the actual browser preview;
  success means editing walk to run displays RUN without a reload. Reproduced HTTP 500 after transcript save: generated theme missing from
  the library. Added Project.theme() project-local snapshots and recovery from embedded preview themes, used by compose_project.
  tests/test_caption_live_edit.py passes both all-format correction and missing-theme recovery regressions. Reapplied the already-saved run
  correction on the restarted local Studio :8878. In Chrome, changed run→walk→run through the caption field and confirmed the preview
  visibly reads RUN EACH at ~2.55 seconds without refreshing. Latest Studio typecheck/build passes. No export or narration change claimed;
  this verifies the editable video preview. Full UI-audit suite remains pending, not passed.
- 2026-11-02: Simplified the everyday desktop flow after visual testing. Projects no longer interrupts with a setup banner. New Video is now
  exactly three steps: add content, choose posting shape, create. Every optional choice remains visible on the final screen in plain language
  (language, style, director, look, music, captions, voice, pace, speech cleanup, length, sound effects, unusual words and own pictures).
  Settings now starts with three normal choices and keeps the complete settings list visible below with human labels; there is no hidden
  Advanced section. Remote GPU services are configured at 192.168.123.47 (Ollama 11434, ComfyUI 8188), and the UI reports the GPU server as
  connected without exposing technical details in the normal flow. Electron visual checks passed for Projects, all three New Video steps,
  the full visible choices screen and Settings. Verification: Studio production build passes; desktop `npm run test:director` passes;
  `.venv\\Scripts\\python.exe -m pytest tests/test_director_choice.py -q` passes 6/6. Running the system Python instead of `.venv` fails
  collection because that interpreter does not have httpx; this is an environment mismatch, not an app failure.
- 2026-11-02 editor workflow/precision pass: inspect pointer-to-time handling, save races and panel layout; verify exact timing against
  the live Studio on a disposable copy and with regression tests, then visually exercise the rebuilt app when the desktop is available.
  Implemented automatic app-sidebar collapse, explicit panel/focus toggles, task-based left navigation, context-based right controls,
  precise time fields and understandable timing labels. Fixed final pointer release coordinates, handle offsets, exact splits, source
  offsets when trimming, fades after shortening, locked tracks, stale save/refetch responses and phantom undo steps. Scene splitting now
  shows actual sentence choices; it no longer silently moves a click to another time. Scene-boundary drag previews match their landing.
  Added live local layer preview updates, pending element-save flush, selection exclusivity, narrow-window timeline access, responsive
  preview sizing and form/dialog-safe shortcuts. Voice edits are serialized without accepting stale output coordinates while saving.
  Validation: Studio production build passes; 13 Node timeline/save-race tests pass; focused Python audio/layers/caption selection passes
  with one optional skip. Live API QA on 2026-11-02-why-do-small-habits-matter-copy verifies split at 2.137s, cut exactly 0.500s, mute/gain,
  undo/redo, and layer text/timing/position/opacity in portrait, square and landscape data. Baseline restored; user's original untouched.
  Full pytest is running in docs/evidence/editor-full-tests.log. Found/fixed frontend API expectation 6 vs backend 7; targeted test passes.
  Visual sign-off is outstanding: Windows is locked and Cua cannot activate Chrome. Asked user to unlock; did not bypass the lock or
  claim visual QA. The revised layout must still be inspected and exercised in the live UI. No new rendered video/export claimed.
  Follow-up validation: remaining backend selection completed in 233s (375 passed, one stale music-catalogue test failed). Repaired that
  test using a real isolated catalogue for preference/variety, with separate fallback and actual bundled-track checks; all five music
  tests now pass. No music-selection behavior changed. Full pytest remains in slow real-recording ASR equivalence at 20:24; its first
  API-version failure is fixed and separately verified. Windows still locked on the final Cua check. No visual pass or full-suite pass claimed.
- 2026-11-02 follow-up plan: cloned and inspected Concat/Filmcraft source and screenshots; cross-checked existing components, layers,
  renderer and director/MCP catalogue. Recorded scope and acceptance in docs/plans/PLAN-RESPONSIVE-EDITOR.MD before implementation.
  Priorities: canonical scene-boundary destinations and loss prevention; shared searchable component browser; a fully integrated Shape
  component; compact responsive layout; actual UI checks when Cua permits. Existing 39 components and layered editing will be reused.

- 2026-11-03 continuation plan and outcome: finish free editor semantics first, then compare docs vision against registered modules, UI routes and actual Director discovery. Implement shared connections rather than new isolated controls; verify model persistence and all aspect ratios, then run UI checks.
  Replaced sentence-bound edges with exact seconds, enabled independent visual/action/caption timing, live drafts, sound extraction and caption history; removed data-dropping overlay/SFX limits and automatic removal of edited visuals; fixed action index stability and split duplication. Added real renderer library previews and opaque dropdowns, reversible Video settings and responsive panels.
  Audit found module discovery schemas were truncated and new editor actions/graphics were unavailable to the Director. Shared exact editor functions now drive timeline.edit_scene; timeline.place preserves canonical components, rejects unsupported fragments before saving and recomposes previews. Agent discovery retains complete catalogue/schema data and includes described tools in its recent working set. Studio exposes the registry under AI → All video tools, with ordinary forms, prerequisites and results. New offers all existing caption styles and optional closing line. Fixed settings stale overwrite, narrow address field and false connection claim.
  Evidence: docs/AUDIT-2026-11-03.md and capability-inventory.json (165 modules, 135 autonomous, 40 components, 162 routes, 18 pages, clean registry). 41+1 initial editor, 113 expanded, 69 final focused Python cases; 17 Node behavior tests; Studio build, desktop Director runner and docs checker pass. Live disposable-copy precision QA passes and restores baseline. Real free-visual frames inspected; independent character/shape frames rendered. Full and fast regression logs are still running at this checkpoint; one stale 39-component assertion was repaired and passes in the focused rerun. No full-suite or fresh interactive visual pass claimed. No remote deployment or social posting performed.

- 2026-11-03 fresh UI acceptance and final corrections: Cua now works. Verified the disposable copy in desktop, 960px and 400x664 layouts, actual Title example, opaque operation dropdown, settings return, live RUN-to-SPRINT caption draft and Escape cancellation, exact boundary drag to 1.879s and undo to 1.600s. Caption editing moved from a preview-covering modal into Details; transcript typing now previews too. Reset tab scroll, corrected whole-video helper copy, protected mobile time-field width, and added typed custom tool details. Normal desktop restored; original project unchanged.
  Fixed fill.graphic slot timing override and English language-detection fallback. Broad non-slow run completed: 1142 passed, 4 skipped, 3 stale assertions failed; 15-case and final 48-case reruns pass corrected assertions. Latest Studio build and 17 Node checks pass; capability inventory remains 165/135 autonomous/164 forms/40 components/162 routes/18 pages, clean lint. Local Studio restarted PID 34584; live precision API QA passes and restores baseline. Slow full regression 26011 remains running, last 65%; inspect final failures before full sign-off. Audit and handoff updated; no deployment, posting or commits.

- 2026-11-03 new scope plan: rebuild sharing around selecting any project, then export readiness, account selection and a single post composer; replace credentials JSON with platform-specific fields and reuse account groups as optional shortcuts. Redesign Shorts around source → picks → editable clips, simplify Media into visual tabs and a contextual item panel, and reduce Inspector clutter without removing capabilities. Audit installed skill docs plus the two supplied repositories and linked capabilities; adapt them as fixed reusable character/environment/motion/text presets through the canonical renderer, Director, API and UI. Rename the product Ultimate Video Tool; validate and repair Windows/Linux client/server packaging and CI, build installers, test local installation, and release only the concrete tested distribution. Verify backend contracts with isolated mocks, visual UI using Cua, real render samples, installer smoke checks and artifact checksums. Preserve the existing uncommitted source and user projects.

- 2026-11-03 skills/Direction continuation: implemented the selection-first Share/Shorts workflows, compact inspectors/media tabs, reusable story kit, Three.js environments, canonical animation keyframes, 16 templates and shared Director capability modules. Added per-scene editable Direction, model/prompt choices, recorded generation history, image/video regeneration and universal scene voice replacement. Fixed voice edits regrouping beats and breaking scenes; hidden caption anchors now survive shorter replacements. Exact timing and one-step voice/caption undo are tested. Added generation conflict guards and retained Direction drafts/jobs across tool switches. Full checkpoint before Direction: 1172 passed, 4 skipped. Latest Direction/voice/motion/words/pipeline: 33 passed. Studio build and 19 Node tests pass. Earlier story/motion rendered evidence was inspected. Latest Cua retry still reports local browser use disabled; no fresh UI sign-off. New caption-render verification is running in direction-render.log. Updated audit records capabilities and limitations; old installers are stale, final release pending. No remote service changes, posting, commits or pushes.

  Follow-up: qa_direction.py completed; inspected real rendered “Run every day.” captions in portrait, square and landscape, with exact undo restoration. Documentation checker passes after resolving archived research links to upstream. Restarted local :8878 and verified the disposable-copy Direction endpoint exposes seven picture recipes and two video workflows. Corrected narration defaults to follow exact scene timing after boundary edits, rather than old beat ownership; regression added. Fresh interactive QA still blocked by the local-browser Work setting.

- 2026-11-03 browser access restored: in-app browser now works. Restarted the stopped lab Studio on :8878 (launcher 35572) and visually tested the disposable copy. Direction draft survives tool navigation; picture/voice controls load; live RUN → SPRINT appears in the actual preview and Escape restores RUN; Video settings toggles back to caption selection. Typewriter preview renders; insertion exposes Motion controls; Slide creates editable animation points; two undos restore one original scene component and clear undo. Checked 1440×900 and 400×760. Found excessive tool-header height; changed tool navigation to two rows and Direction tabs to one row, rebuilt and inspected the improved mobile drawer. Share accepts an unexported project and shows its Export action; Accounts onboarding and Shorts Upload/Your videos entry screens inspected. This is focused visual acceptance, not all options or real GPU generation, social posting, installer/release acceptance. Browser viewport override reset; IAB tab marked for continuation. Latest Studio build passes (visual-resume-build.log).

- 2026-11-03 home-only remote installation: owner explicitly authorized SSH installation and chose existing ComfyUI. Fresh app/data/private Python CPU env/private Node/renderer in /home/roy/ultimate-video-tool-server; full web UI on :8790, own enabled user service active at login. Added full-server archive option with Studio/assets. Existing engines untouched. UI paired and inspected with zero projects; New defaults show Best available director and Best available voice (Breeze/OmniVoice), with Director voice casting. Fixed old Edge defaults in creation, scene defaults and Director modules; explicit selections retained. Actual Breeze speech 2.24s, Klein image, frame and 1080×1920 H.264/AAC export passed; frame inspected. 28 core/packaging and 19 module tests pass; final defaults regression and Studio build pass. See docs/ops/home-server-2026-11-03.md. Linger disabled, so boot-before-login is outside this home-only scope. No password stored in files.

- 2026-11-03 architecture correction: implemented independent desktop native Claude/Codex companion and selected processing-server ownership. Added Codex routing, paired-device run ownership, reconnect/readiness/cancellation, worker-based status checks and same-version runtime fingerprint refresh. Server setup now discovers existing engines, validates server-native storage roots, snapshots install choices, selects GPU/fitted picture files, assigns separate managed-engine ports, offers empty-Ollama model preparation, and checks existing Comfy missing files directly in the four-step wizard. Fixed two setup response/save contract bugs and ambiguous loopback/capability wording. Deployed only the isolated /home/roy Video Tool service; visual connection and existing Klein workflow readiness passed. Real local Codex MCP read-only call passed; focused Python and three Node suites/Studio build pass. Rebuilt Windows installer with companion files verified; installation smoke test still underway. Details/limits in docs/evidence/client-server-acceptance.md.

Final architecture acceptance: architecture-acceptance-final.xml reports 45 passed / 0 failed. All three native Node checks and docs checker pass. Windows installer upgrade exited 0, installed companion files verified. Previous connection choice preserved in connection-before-server-architecture.json; current desktop choice targets http://192.168.123.47:8790 as authorized. Installed app startup log confirms that target and its Studio window is enumerated. Native window inspection hit app approval timeout, so do not claim native visual acceptance; browser setup/connection/model readiness/final Done were visibly verified. No verification processes intentionally left running.

## Product directory split — latest, 2026-11-03

Owner explicitly rejected a workspace bundled with the server. This supersedes the combined server-edition architecture above. Physical roots are client/ (studio + desktop client/companion/protected UI proxy) and server/ (vt + renderer + design/assets + desktop server manager + packaging + pyproject/uv.lock). No root symlinks. Root pyproject is pytest configuration only; root .venv is retained as the existing test tool environment. User projects/data remain in their original locations; no storage ownership migration was inferred.

Client now loads its own built UI through a session-protected loopback transport, with isolated per-processing-server Electron cookie partitions; API/media/WebSockets go to the selected server. It ships only ws as a production dependency and no Python/server bootstrap/resources. Server API no longer has an editor SPA fallback. Its / and /manage are standalone management pages, and native managers use Engine settings, not Open workspace.

Remote .47 API now serves management only; old app/studio files were moved to a separate /home/roy legacy backup. Linux GTK manager remains a user-home app/tray control (Electron sandbox unavailable; no system security changes). Both Windows products have separate manifests/locks/builds; inspected client resources are app.asar + studio, inspected server resources are app.asar + app-src with no Studio. Final installers built (client ~82MB, server ~237MB); per-user upgrade smoke test is underway. Preserve old data.

Node transport, companion, Director runner, server ports/control/bootstrap tests pass. Developer scripts implemented with private Node/uv/Python, role selection, updates, isolated dev data, launchers and JSON readiness. Real isolated client-only install/update with spaces and preserved data passes, plus PS parse/check. Full clean Linux development installation not yet accepted. Backend tests and final docs/installer checks still underway; inspect product-split-final.xml/log and package logs. Local Vite :5173 is running client UI against .47; paired and visually confirmed projects + New flow. IAB server tab is management; local client tab is the separate editor. Do not claim every historical task/test or native UI audit is complete.

- 2026-11-03 contained server UI: Engine settings and logs now remain inside the native app, with Back navigation, on Windows/Electron and Linux/GTK-WebKit. Removed external browser/log editor launch paths, restricted embedded navigation and native IPC, added action plus actual UI-state tests. Linux manager deployed and WebKit process checked. Server management embedding policy deployed to the isolated home-only service. Focused product acceptance: 54 Python passes, 12 overlapping boundary guards, 9 storage/caption/path passes; independent developer client install/update tested on both OSes. Native visual click-through remains explicitly unaccepted.
- Windows containment upgrade exited 0. Installed internal engine/log views verified in app.asar; retained runtime refreshed and API returned to healthy operation. Final artifact hashes refreshed and docs checker passed (252 links, 489 paths/tests, 13 phases).


## 2026-11-03 — Recording pipeline and GPU correction

Restored original 1920×1080 canvas and normal captions after owner rejected the extra band. Ran the real Pipeline.run and production export. Rejected/quarantined a frozen-source export; fixed HyperFrames runtime video discovery by inlining the actual video factory. Real eight-second source-frame checks passed on Windows and Linux. First recording now has two checked exports locally; second recording remains in the active batch. Music for the original second recording is queued next; full-screen motion cutaway experiment is deferred. See docs/ACTIVE-WORK.md.

Owner requires GPU whenever available. Removed QA CPU override, made UI acceleration automatic, added actual NVIDIA encoder probes and CUDA selection respect. Initial browser GPU test selected V100 despite pinned NVENC; fixed Linux browser binding with Vulkan and ANGLE device selection. Subsequent real browser probe names RTX 3060; NVENC also verified RTX 3060. Hardware eight-second render passed source comparisons (errors 1.154 and 0.885 at 480×270). Renderer now records acceleration logs/reports and shows fallback reason; incomplete hidden render files are excluded from export listings. Current 32 focused Python tests, 23 timeline tests and client build passed. No claim of clean cross-platform production acceptance; no commit/push/release performed.

## 2026-11-03 — Owner stop; documentation-only handoff

The owner stopped all work, requested cleanup and CLAUDE-HANDOFF.md, then explicitly prohibited further coding and asked for documentation only. Remote QA process tree and local Vite PID 42580 were stopped; existing installed engine services were not stopped. A comprehensive cleanup pass was not executed. No further coding/tests/builds/renders/cleanup are authorized. Full change/state summary is in CLAUDE-HANDOFF.md and supersedes earlier running/completion claims.

A local RTX 4050 test export was mistakenly launched despite the remote-only processing instruction; it had exited when checked. The owner explicitly objected. GPU-by-default production behavior is not permission to run the client PC GPU. This boundary is recorded in both handoffs and the stopped queue.

Final read-only inventory found the remote data/projects directory empty, with no cause established. The download helper's direct sftp.get destinations were truncated when the remote MP4 references failed. Three local MP4 paths are zero-byte and invalid; prior successful source/visual checks do not make them deliverable now. Source recordings, code, subtitles, PNG evidence and manifests were not removed by a cleanup pass. Atomic download replacement remains unimplemented because coding was stopped. Recovery/recreation requires a new owner instruction. Do not resume the historical queue automatically.

## 2026-11-03 night (Claude): clean reinstall, recording 2, server stats, GPU assignment, client UX
- Cleaned both machines (only Video Tool's own folders), reinstalled from scratch: server package + `scripts/lab/install_server_fresh.py` (cu124 build now chosen by `install-engine.sh`),
  native manager + Applications entry, client installer rebuilt and installed. Details and what was not touched: top of CLAUDE-HANDOFF.md.
- Recording 2 (`2026-11-02 09-13-35.mp4`) through the full pipeline with music on the 3060: run 1 judged NOT proper (6 black flashes introduced by fade transitions, a wipe-glitch frame,
  a full-screen card over the recording); cause "auto" = generic explainer; fix: a no-face picture video starts in the protected "subtitles" mode. Run 2 started (dist/recording-run-v2).
- New: `vt/sysstats.py` + `vt/gpuassign.py` (API, `vt system`, `vt gpu`, MCP tools, Server page, GPU assignment card); Settings 9 -> 5 sections; dashboard opens the editor while exporting;
  client `--server/--code` command line; safe downloads; English speech model large-v3 on GPU; Linux CUDA library loading; steps spacing; render tests CPU-only.
- Disclosure: my earlier runs of `tests/test_handback.py::test_rendered_frame_after_the_exit_shows_the_picture` and `test_backdrop_render.py` took one browser snapshot each on THIS PC with the
  default `gpu=True` (possibly the RTX 4050). Both now pass `gpu=False`.
- Plans: `docs/plans/PLAN-CLIENT-UX.MD` (this redesign), `PLAN-DIRECTOR-CHOICE.MD` (already built by Codex: Claude on this PC is listed and first in the order when the app is open), `PLAN-CLOUD-AI.MD`.

### 2026-11-04 (Claude) — recording 2, run 3 and command line
- Protected recording path used theme "auto" (not a real theme) and failed at compose: now `minimal` (server/vt/pipeline.py). Deployed to the GPU server.
- Command line documented in client/README.md: `--server=URL --code=CODE` (the `=` form; the space form can exit the app).
- New checker: `python scripts/lab/judge_recording.py <edited.mp4> <original.mp4>` (introduced black flashes, music vs speech level, captions, contact grid). Run 1 failed it (6 introduced flashes, music only ~9 dB under speech). Run 3 verdict: PASS on picture (0 introduced black flashes, full screen kept, 343 captions, duration kept); music sat 10 dB under speech (judge said too loud) so the default music_volume went 0.14 -> 0.10 (schema, mux, SoundPanel). Needs a re-run to confirm.
- Still open: silent uninstaller leaves program files (cause unknown).

### 2026-11-04 (Claude) — sound mix controls, preview speed
- New options: `duck`, `duck_amount`, `duck_release`, `target_lufs`, `music_fade_in`, `music_fade_out` (schema, mux, pipeline, export body). Music level is shown in dB (0.10 = -20 dB). Component `client/studio/src/components/MusicMix.tsx` is used in the editor Sound panel and on the Export page; each setting is marked Automatic (system default) or Yours (with reset).
- A smoke test caught an unconnected ducking output when ducking was off; fixed. tests/test_music_mix.py covers every setting.
- Preview playback: the loop draws every other frame when the page is slow (sound stays the clock) and updates the clock/slider ~15 times a second (client/studio/src/review/Preview.tsx).
- Client installer rebuilt (dist/fresh-2026-11-03/client) and installed silently; server code deployed to the GPU server.

### 2026-11-04 (Claude) — jobs on the Server page, desktop/web coherence, icons
- Jobs: every job keeps its own log (steps + log lines + trace on failure) in server/vt/server/jobs.py; GET /api/jobs/{id}/log?after=N; Server page has a Jobs panel (client/studio/src/components/JobsPanel.tsx): progress, stage, elapsed, ETA, Stop, "Show details" opens a followable log with Everything/Steps/Problems filter, copy and save. tests/test_job_log.py.
- Desktop vs web: Select (batch) and search on the dashboard only appeared with 3 / 9+ videos; now they show with 1+ (filters with 2+). "Show in folder"/"Open folder" now opens only when the request is from the server's own computer; otherwise the app says where the files are on the server (client/studio/src/openFolder.ts).
- Engine cards (Language AI / Pictures and clips): the "Picture models" block now sits inside the card's rows; results use a status line with a dot.
- Icons: client orange, server blue. The Windows exe icon was missing because signAndEditExecutable=false skips rcedit: embed it with rcedit-x64 on win-unpacked, then `electron-builder --prepackaged`.

### 2026-11-04 (Claude) - option pages, director's script review, HyperFrames pre-flight
- New video, last screen: every choice is a tile (Automatic/Yours) that opens its own page of visual cards (client/studio/src/pages/NewOptions.tsx + new-options.css): language, style, edit mode, director, look, music (listen to tracks), captions (real previews), voice, pace, clean-up, length, sound effects, words, pictures, and Director's script. No drop-downs.
- Director's script review (server/vt/server/script_review_routes.py, client pages/ScriptReview.tsx, route /p/{id}/script): scenes next to their words with what the director chose; layout and transition editable (scene PATCH); feedback to the director for one scene or the whole script (existing request queue; answers come back as options to choose); rounds recorded in script_review.json; approve and reopen. Option review_script (New > Director's script) sends the video here after planning; the editor has a Script button. tests/test_script_review.py.
- HyperFrames: it is the renderer (render + snapshot, GPU selection, fonts, composition contract). Not used before: its own check (lint, runtime errors, layout, motion, WCAG contrast; about 2 s, software browser). Now run before every export (vt/render/hyperframes.py::check, result in exports/.check-<aspect>.json, problems reported in progress), vt check <project>, and GET /api/projects/{id}/script-review/render-check with a Check before making card on the script page. Still unused: beats, audio, transcribe, catalog/add, compare, media-treatment, normalize-audio.

- 2026-11-04 closing pass: dark-theme override so checked option cards stay readable (new-options.css); scripts/build_client_windows.sh builds the installer with the icon embedded; handoffs updated; client reinstalled. Server script-review routes verified live.

- 2026-11-04 evening: explicit choices now win for recordings. Cause of "nothing applied": a screen recording is auto-set to "Keep my video" (recording_edit=subtitles), and New.tsx then forced music=null/sfx=false; the director is never asked in that mode (1 scene, planner=rules), and "Automatic" music was never resolved there (pipeline.stage_plan now resolves it first). screen_recording.layout keeps sfx cues in screen+graphics mode when sfx is on. Script page shows a "kept as recorded" card with POST script-review/add-graphics (switches to screen+graphics and re-plans). New video hub has a "What will happen" box. Server NOT redeployed yet (needs GPU_PASS).

## 2026-11-05 Cartoon 2 (story engine) + Cartoon 1 extras + everything editable
Plan and status: docs/STORY-ENGINE-PLAN.md. Engine source: server/renderer/story/src (rebuild with `node server/renderer/story/build.mjs`; React comes
from client/studio/node_modules). Python: server/vt/story/. Studio: client/studio/src/review/story/, review/JsonField.tsx; Vite/TS alias `@story`.
Tests: tests/test_story_engine.py (8). Do not edit runtime/vt-story.js by hand. Times inside stories are absolute video seconds.

- 2026-11-05: one director per video, AI conversation log, direction-only house rules, SRT input, ElevenLabs engine, Bensound tracks, picture cards for character look, honest progress. Details in CLAUDE-HANDOFF.md.
- 2026-11-05 11:15: the director places elements and reviews its own frames (all three kinds of director); cartoon compiler no longer overrides the director; craft.check crash fixed. Details in CLAUDE-HANDOFF.md.
- 2026-11-05 16:10: opening frame, character arrival and floor, quote spacing root cause, measured frame facts for directors, silent overlay drops and default actor removed, number parsing, UI polish. Details in CLAUDE-HANDOFF.md.
- 2026-11-05 17:00: wrote docs/plans/PLAN-PERFECT.MD (the plan for Sonnet) and scripts/lab/vt_lab.py (its test bench).
- 2026-11-05 evening: plan updated with the owner's decisions: Phase M (helper bundled with the client), Phase K (choosing graphics cards, V100 stays for training), overlaps decided, names and default model agreed. No code changed for these yet.
- 2026-11-05 21:18: plan step A1 done: 184 changed files on main (last commit 4d544a6); vt_lab.py report 2026-11-05-final4 printed status rendered, director local, 59 AI conversations; key file present.
- 2026-11-05 21:19: plan step A2 done: deploy printed health: {'ok': True, ...}; the saved primary card GPU-a1b5ab18 is the RTX 3060 (index 1). The V100 showed 90% load from the owner's own python3 training.
- 2026-11-05 21:31: plan step A8 done: npm run test:timeline 23/23 pass; npm run build (tsc + vite) ok; client/desktop npm test (companion, director runner, transport) ok; server/desktop npm test (3 files) ok; check_docs.py --fix-facts rewrote only the counts in the STATUS.md facts table (40->41 element types, 37->43 MCP tools, 247->264 API routes, new pages NewOptions/ScriptReview/Server...), then check_docs.py reports no PROBLEM.
- 2026-11-05 21:40: plan Phase A started. A1, A2, A8 done. Test-side fixes made for A4 items 1-3 (leaking Chrome path, onnx provider tuple, tunnel isolation), `--disable-gpu` added to all browser suites, optional VT_SERVER_KEY in the Studio's Vite proxy, `scratch start|stop` added to vt_lab.py (not run yet). The GPU server restarted by itself during the A3 baseline run (also at 16:59 during the earlier run); see docs/evidence/perfect/A3-server-restarts.md. Heavy server runs paused until the owner answers.
- 2026-11-05 21:48: plan step M1 done: docs/evidence/perfect/M1-before.md: Claude and Codex on MSI-LAPTOP listed with the app open and gone after the window closed (also not back after the server restart); NoProvider shown to give every other AI step no AI.
- 2026-11-05 22:05: plan step M2 done: client/desktop/helper.js + test-helper.js (in npm test, passes 5 runs, two deliberate breakages fail it); idle memory 59.4-60.7 MB under plain Node (limit 80). The old companion and its test stay until M6. See docs/evidence/perfect/M2-helper.md.
- 2026-11-05 22:05: plan step M3 done: ask for Claude and Codex in director-runner.js/codex-runner.js, tested with stand-in programs (and mutations); real Claude: picture read as BANANA, outside-file read and shell command refused, run offers 0 built-in tools and still calls list_projects. Found that the old direct flags let a shell run. Codex only against a stand-in. See docs/evidence/perfect/M3-lockdown.md.
- 2026-11-05 22:31: plan step M4 done: ClientProvider + DirectorBroker.ask + director_model + the video's director scope for jobs; NoProvider removed; fake-device test shows understanding, planning, last look (with pictures) and title all go to the laptop and no other mind is asked; 6 mutations caught; 110 passed on the server (uptime unchanged). See docs/evidence/perfect/M4-every-ai-step.md.
- 2026-11-05 22:47: plan step M5 done: 90 s grace with re-send on reconnect (helper ignores duplicates), plain failure after the grace and a cancel when the computer returns, boot id in hello so a helper drops a restarted server's work, computers remembered as 'Not connected'; failed client director now recorded as rules with a notice. 7 new Python tests + helper tests; 8 breakages caught; 136 passed. See docs/evidence/perfect/M5-interruptions.md.
- 2026-11-05 23:16: plan step M5b done: Pairing removed. A computer on the server's own network connects with the address alone; outside it, forwarded, or via a web page still needs the key/is refused. test_server_auth.py rewritten (25 tests, 8 breakages caught); real server checked with no key from this PC; real helper and the real app (from source, fresh data folder, address only) both registered Claude on this PC with no code. The packaged installer is H1/M6. See docs/evidence/perfect/M5b-no-pairing.md.
- 2026-11-06 07:11: plan step M6 done: The app starts/reuses/replaces the helper and only tells it the server's address; --helper entry, helper IPC and preload, companion removed, package and CI updated. A built app (electron-builder --dir): Node mode runs helper.js from app.asar (no asarUnpack), and after the window closes the helper keeps running and the server still lists Claude on this PC. Also fixed a stop-order race (3 of 6 runs failed before). Idle memory: private 58 MB, working set 83 MB (3 MB over the plan's 80). See docs/evidence/perfect/M6-app-uses-the-helper.md.
- 2026-11-06 07:29: plan step M8 done: the Helper card in Settings and the Computers card on the Server page; 27 browser checks pass (wide and phone, light and dark, English and Bangla), Bangla text for the helper's own sentences, phone buttons 44 px; evidence docs/evidence/perfect/M8-show-the-helper.md.
- 2026-11-06 07:37: plan step M9 half done: vt_lab.py helper start|status|stop (real helper.js, own folder dist/lab/helper, name '<PC> (lab)', VT_HELPER_NAME added to helper.js and tested); the server listed Claude on MSI-LAPTOP (lab) ready; old vt_lab.py direct removed. The make run waits for the owner's answer about renders (docs/evidence/perfect/M9-lab-helper.md).
- 2026-11-06 07:44: plan step K1 done: gpuassign: cards Video Tool may use (allowed list, one-card default before the answer, needs_choice, reset on removal), route/CLI/MCP; tests/test_gpu_choice.py 24 pass, nine breakages caught.
- 2026-11-06 08:01: plan step K2 done: K2: the allowed cards are a fence: apply() at server start, restart_needed, blocked() and every GPU use (renderer fallbacks, encoders, speech, ONNX, torch, System panel, engine starts) follows the list; picked cards keep working on servers set up before the question. Found: the owner's ComfyUI service runs on the V100 (K3/K6). Tests pass; 20 breakages caught.
- 2026-11-06 08:21: plan step K3 done: K3: own engines follow the ai/pictures job cards and restart on change (pids checked), existing engines on a card that is not allowed are reported with an offer of Video Tool's own copy; 183 tests, 20 breakages caught, 11 browser checks. Found: the owner's ComfyUI service is on the V100 (their decision).
- 2026-11-06 08:43: plan step K4 done: K4: the app asks which graphics cards Video Tool may use: switches per card on the Server page, a wizard step with two or more cards, a small dot while unanswered, Bangla; install card choice removed; e2e/gpu_card.mjs 39 checks, 6 breakages caught, 164 backend tests. No restart button yet (E15).
- 2026-11-06 12:11: plan step E10 done: owner's decision 8: the interface is English only. Removed the Bangla dictionary, the language switch and the ui_language setting, and the Bangla checks of the browser suites; Bangla stays a language for videos. tests/test_no_bangla_ui.py (4, 5 breakages caught). Also: the graphics card section no longer breaks the Server page on an older server.
- 2026-11-06 12:30: the owner asked to list everything broken or blocked and finish the rest first: docs/evidence/perfect/BREAKING.md (22 items: 4 wait for the owner, the server stops being the main one). Work continues with what is not blocked; K5 in progress.
- 2026-11-06 12:45: plan step K5 done: K5: vt gpu setup + vt server --gpus, install scripts and Docker ask, the server's own pages and both server windows have the question; found and fixed a nvidia-smi loop (534 calls) in my K2 code; tests with a fake nvidia-smi, 33 browser checks, 19 breakages caught.
- 2026-11-06 12:50: CORRECTION: I wrote (K2, K3, the breaking list) that the owner's ComfyUI service runs on the V100, from docs/ops/comfyui-server.md. Read on the server today: it runs on the RTX 3060 (CUDA_VISIBLE_DEVICES=1, PCI_BUS_ID; /system_stats says RTX 3060); the V100 is empty. The document and my notes are corrected.
- 2026-11-06 12:56: plan step K6 mostly done on the owner's server (not ticked: its last check is a real video): code deployed, only the RTX 3060 allowed, Video Tool's own Ollama on 11444 pinned to it with its own folders and home, gemma4:latest pulled (2 minutes), the owner's Ollama service unchanged, the machine was not restarted. docs/evidence/perfect/K6-the-owners-server.md
- 2026-11-06 12:59: plan step B1 done: B1: every override listed and read (12 rows) in docs/evidence/perfect/B1-overrides.md
- 2026-11-06 18:05: plan step B2 done: B2: the guard only measures for AI plans (facts + Quality check list), rule plans keep it and report to Details, Problems; fixed the guard's own drop and shrink (they did not hold) and made layout fit groups; 50 tests, 17 breakages caught, 21 browser checks.
- 2026-11-06 18:13: plan step B3 done: B3: cut props and 'no room beside the person' follow decision 1 (kept for AI plans, told by the facts); fixed the guard log that lost the props; 11 tests, 5 breakages caught.
- 2026-11-06 18:19: plan step B4 done: B4: no silent script repairs: notes for 35 kinds; strict (MCP) errors for changes of meaning, 'repairs' for the small ones; local AI shows them in Details, Problems; 44 tests, 11 breakages caught.
- 2026-11-06 18:25: plan step B5 done: B5: Cartoon 2 no longer drops or replaces silently: notes, strict errors over MCP, all warnings returned, Details/Problems for the rest; prompts updated; 15 tests, 10 breakages caught.
- 2026-11-06 18:30: plan step B6 done: B6: reel path read: nothing overrides the director; approving with open checks is now written down; 7 tests, 6 breakages caught.
- 2026-11-06 18:40: plan step B7 done: B7: every style proven (explainer, stick, emoji, cartoon scripts; story and reel through B5/B6): 89 checks in test_director_authority.py; restoring the old guard fails them; scenery rule for set decoration.

## 2026-11-06 — Codex continuation: queue reliability and restart recovery

- F6 — Done by codex. Reproduced twelve duplicate jobs from simultaneous requests, then made busy-check/registration atomic. Added queue/order/cancellation regressions and locked collection snapshots.
- F1 implementation — Done by codex; plan step remains open for a real scratch-server restart. Jobs persist under projects/.jobs, startup marks unfinished work interrupted, legacy Processing projects recover, and the dashboard/Progress screen offer Continue using valid stage caches. Reconnect replaces stale job state. Detailed prior job logs are not persisted; retention is still F11.
- Checks: combined targeted Python run 20 passed (56 deselected); built Studio recovery browser test passes at 1280/light and 400/dark with fake HTTP/WebSocket responses, screenshots viewed; TypeScript/build and 32 timeline tests pass. No video render, GPU work or speech recognition on this PC. See docs/evidence/perfect/F6-many-jobs.md and F1-restart-recovery.md.
- Owner answered in this chat: keep renders paused and finish unblocked code first. No server access/deployment/restart, commit or push performed. The pre-existing server/debug.log change was preserved.
- Reconciled B8/B10/B11 ticks with Claude's existing evidence and the earlier 175-test passing audit; credit remains Claude implementation, Codex verification. E17 remains unticked because its documented remaining controls/warp limitations are still open.

## 2026-11-06 — Further implementation - Done by codex

- Completed and checked C5, E2, E7, E9, F2 and F4 in PLAN-PERFECT.MD. Evidence: docs/evidence/perfect/CODEX-IMPLEMENTATION-2026-11-06.md.
- C5: real GSAP word-motion recipes work on inline-block spans in English and Bangla; missing-CSS mutation fails the test. Software text fixtures only, no video render.
- E2: shared visual DirectorChoices and StyleChoices on New and Direct again; nine styles, all six directors; project-only run choices, no global provider/model edits.
- E7/E9: redundant dashboard New removed; phone filters folded; five phone tabs with More for Looks/Settings, all destinations reachable with 44px bottom targets.
- F2: cancellation bypasses error fallbacks, preserves checkpoints, reports cancelled in the module log and at late job return, and offers Continue. Tests cover all twelve stages with fake work and actual API/module cancellation.
- F4: disk-full upload/job messages, actual resumable offsets, partial writes and atomic prior-document preservation. Upload tests now use a temporary store.
- E17 implementation gaps coded: twelve value diamonds, projective pin inversion for tilt/slant, static media-layer transforms with schema/history/runtime support, rounded corners without crop. Full editor/export gate remains open.
- E15 implementation coded: verified systemd user-service restart only when MainPID is this process; atomic idle job fence, failure recovery, no button without a supervisor; server numeric wording removed. Tests mock every system command. Full Server-page acceptance remains open.
- E8 tile values wrap; full flow remains open. F10 clamps progress/logs and rejects stale earlier-stage heartbeats; real-run sample remains open.
- Final relevant Python selection: 72 passed. Existing API cancellation: 1 passed separately. Studio TypeScript/Vite build and 34 timeline tests passed. UI fixtures passed in four modes for transform controls, redo and dashboard/navigation, plus six restart states, four word-motion cases and four interruption/cancellation cases. Screenshots inspected. Facts-only STATUS.md refresh reviewed.
- Owner's render pause remains in force. No GPU/model/speech work, real video exports, owner-server access/restarts, autostart registration, commits or pushes. Existing unrelated edits preserved.
- Remaining work is still substantial: C1-C4/C6-C10, D/video acceptance, most E app polish, further reliability/security/retention, G/H/I and owner-only gates. Do not report the rest of the plan complete.

## 2026-11-06 — Frame measurements and readable Details - Done by codex

- C6, C7 and E5 completed and marked Done by codex in PLAN-PERFECT.MD. Evidence: docs/evidence/perfect/CODEX-FRAME-DETAILS-2026-11-06.md.
- Production frame measurements now cover named stick and Story cartoon faces plus photos with detector face metadata/object-fit crops. Story bundle rebuilt. Shared probe tested with actual stick/Story/media factories and software DOM fixtures; no video render.
- Added measured text size, solid-background contrast, portrait platform zones and partial opacity facts. These inform the director/Quality check and change no elements.
- Details opens with tabs visible, groups conversations by step, previews the question and displays retained image attachments. PNG/JPEG/WebP bytes are stored once per hash under the video, served through a project-scoped validated route. Older records say pictures were not retained; image-write failures keep the text record. Attachment retention remains F11.
- C8 partial: facts lead the single-revision prompt; refused edits now name the actual field/reason. Real gemma acceptance and grounded visual suggestions remain open.
- Checks: broader revision/conversation/Codex/one-director run 43 passed; final revision/conversation/image regressions 7 passed (overlapping selections). Studio build and 34 timeline tests pass. Frame checks and Details browser fixture pass; Details checked wide/phone, light/dark with screenshots viewed. Live-server log.mjs selectors updated, that suite not run.
- No real renders, GPU/speech work, model calls, deployments, server restarts, commits or pushes. Owner render pause remains active. No claim that the whole plan is complete.
- 2026-11-06 23:18: plan step E17 done: E17 done: full per-element transform editing, human in the loop.
- 2026-11-06 23:18: plan step B8 done: B8 done: Claude model choice, real runs checked.
- 2026-11-06 23:18: plan step B10 done: B10 done.
- 2026-11-06 23:18: plan step B11 done: B11 done.
- 2026-11-06 23:40: plan step F1 done: F1 verified by a real kill and restart of the scratch server.
- 2026-11-06 23:46: plan step F8 done: F8: closed the /mcp/director path bypass and symlink log paths.
- 2026-11-06 23:47: plan step K6 done: K6 done: real gemma video, cards sampled.
- 2026-11-07 00:07: plan step C10 done: C10: goldens refreshed after review; server suite run, failures triaged.
- 2026-11-07 04:08: plan step C1 done: C1: wide and square cartoons rendered on the server, feet on floor, captions clear; sticker over faces is the director's choice and is reported by facts
- 2026-11-07 04:13: plan step C2 done: C2: qa_sets.py written, set layers widened to 1200, 30 contact sheets looked at, no edge gaps
- 2026-11-07 08:40: plan step C9 done: C9: qa_preview_export.py, snapshot vs MP4 in 3 styles x 5 moments match
- 2026-11-07 09:12: plan step C8 done: C8: 3 gemma videos checked; found and fixed a stale Quality check after the viewer-test revision (remeasure); big sticker over faces is gemma's limit
- 2026-11-07 09:44 the GPU server went down: power cut (owner). Server steps wait; local work continues. C1, C2, C8, C9 ticked earlier today.
- 2026-11-07 09:56: plan step E1 done: E1: GLOSSARY.md, renamed Studio/server/doc words to one name each
- 2026-11-07 10:31: plan step E6 done: E6: editor suite updated and passing; editor_simple retired
- 2026-11-07 10:31: plan step E8 done: E8: New tiles full values, suites pass
- 2026-11-07 10:40: plan step A3 done: A3: full suite green on the server, goldens b refreshed, byte-identical test fixed (frozen director clock)
- 2026-11-07 10:40: plan step A4 done: A4: full suite green on the server, goldens b refreshed, byte-identical test fixed (frozen director clock)
- 2026-11-07 10:40: plan step A5 done: A5: full suite green on the server, goldens b refreshed, byte-identical test fixed (frozen director clock)
- 2026-11-07 11:28: plan step E11 done: E11: every page in loading/empty/error/unreachable; error boundary, plain error words
- 2026-11-07 11:28: plan step E12 done: E12: contrast fixes, arrow keys in radio groups, keyboard suite
- 2026-11-07 11:43: plan step E15 done: E15: Server page checked, job kind words, parallel engine probes
- 2026-11-07: E16 partial: connection banner and auto-reload added; address typing and app update wait for the real app (H1, H3).
- 2026-11-07: E14 partial: 10-minute timeline measured, nodes cut 35%, still janky without a GPU; scenes-stay-laid-out is the next lever (BREAKING).
- 2026-11-07 12:20: plan step A6 done: A6: browser suites run against the server's scratch with the proxy key
- 2026-11-07 12:21: plan step H7 done: H7: packaging tests and set_version checked
- 2026-11-07 13:01: plan step H6 done: H6: build_server_windows.sh, installer rebuilt with the right icon
