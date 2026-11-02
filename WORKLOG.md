# Work log

Newest first. Every agent (Claude Code, Codex) adds an entry when it stops: what it did, what it verified, what is left. Read
`CODEX-HANDOFF.md` first.

## 2026-11-02 (Codex) — director choice (implementation complete; local live paths verified)

**Plan:** Build the director registry and fallback selection as one shared `vt/` capability, expose it through `/api/directors`, project
creation, CLI, MCP, and the Studio New/Settings flows, then connect the desktop WebSocket client so a logged-in local Claude can answer a
remote server's directing request with Video Tool MCP tools only. Verify registry/selection, fake-device completion, timeout fallback, and
tool allowlisting with focused tests; then typecheck/build Studio, run the related suite and full pytest, restart the lab Studio, and make
and judge the billionaire comparison through the real UI and GPU path.

**Built:** `vt/directors.py` owns the live registry, fallback policy and targeted request broker; `/api/directors` and a revocable
desktop-director MCP token are exposed; project options and metadata record the requested/resolved director and fallback reason. Reel and
ordinary plan paths now honor client Claude, server Claude and local fallback. The Studio New flow has a director step, Settings has order
and timeout controls, Review shows attribution, CLI creation commands accept `--director` and `vt directors` lists availability, and the
MCP `project.create` input carries the same choice. Electron detects/login-checks Claude, announces over `/ws`, runs it with only
`mcp__video-tool__*`, streams logs and reports completion (`desktop/director-runner.js`). Local Electron uses the bundled Python stdio MCP;
a client attached to a remote server uses a revocable HTTP MCP token. MCP now exposes `get_reel_plan` and `check_reel_plan`, including full
self-contained picture prompts and actionable `picture.place` / `picture.drawable` issues. Reconnect races, failed sends, Claude process
launch on Windows, one-token-per-session behavior, provider failure fallback, and accurate rules attribution were also closed.

**Verified:** all 6 `tests/test_director_choice.py` tests pass (targeted completion, absence, reconnect race, send failure, prompt/tool names,
reel-plan MCP payload/checks, API registration). The existing non-ASGI plan tests reached 15 passes before the first TestClient test was
stopped. Electron syntax and `npm run test:director` pass, including both stdio/HTTP MCP definitions and the exact tool allowlist. Python
compiles; schema construction, CLI listing/help, `git diff --check`, and the backspace scan pass. Studio `npx tsc --noEmit` and `npm run
build` pass. A real Studio was started on port 8878 and the New page loaded visibly in Chrome.

**Live verification resumed at the owner's request:** rebuilt `studio/dist`, started the real Studio on port 8878, and drove the complete
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
- **66 film styles from lemo-opuscar** (MIT): `scripts/import_lemo_styles.py` -> `design/styles/<slug>.json` (style bibles) +
  `design/themes/style-<slug>/theme.json` (palette from the bible or its poster, its typeface, WCAG contrast, `picture: line` for drawn looks).
  26 typefaces added (`renderer/scripts/build-fonts.mjs`). `vt/styles.py`, modules `style.list` / `style.get`, `vt styles`, `/api/styles`.
  Planning and script tasks now carry `craft_rules`, the chosen `style` bible and the current `craft_report`.
  Gallery: `scripts/style_gallery.py` -> `C:\Users\Roy\Videos\Video Tool Lab\styles-gallery\index.html` (3 frames per style).
- **Remote Claude**: MCP `prepare_upload` gives a curl / PowerShell line with a one-time ticket (`PUT /api/uploads/<id>/file?ticket=`);
  `create_project` / `add_media` take `upload:<id>`. Test in `tests/test_upload_resume.py`.
- **Every NVIDIA GPU**: `vt/gpu_detect.py` (cu128 RTX 50 / cu124 default / cu118 old drivers / cpu), torch builds are uv extras
  (`--extra cu124` etc., one `uv.lock`); setup.ps1 / setup.sh / desktop bootstrap pick it; `vt doctor` shows "GPU build". Local: cu124.
  **Sync command is now** `.tools\uv.exe sync --extra dev --extra cu124`.
- **Timeline**: `studio/e2e/perf_timeline.mjs` measures frame times + Chrome layout/script costs. Fixed: timeline rebuilt on every clock tick
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
- Spoken compound numbers ("eighty four percent" = 84 %, was shown as 4 %): `vt/planner/rules.py`, `tests/test_spoken_numbers.py`.
- Captions: phrase splitter (2-3 words, max 4; never end on a function word; never split a number; no lone words; appear 0.06 s after the word).
- Craft rules module `vt/craft.py` (24 rules with sources, 10 measured), modules `craft.rules` / `craft.check`, pipeline writes `craft.json`
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
- `vt/engines/fit.py`: the VRAM calculator (weights at run precision + working memory + CUDA share; RAM = parked models + a read buffer).
  Picture "recipes" for the same Z-Image graph: zimage-full (bf16, 24 GB+), zimage-fp8 (UNET weight_dtype fp8_e4m3fn + Comfy-Org
  qwen_3_4b_fp8_mixed: 12/16 GB), zimage-fp8-small-text (fp4_mixed text reader: low RAM), zimage-nvfp4 (RTX 50). A set is picked only with
  15 % headroom (COMFORT) unless nothing else fits; partial offload only as a last resort. Language model by card: gemma3 12b/4b/1b.
- `vt/engines/discover.py`: scan a host (usual ports, or every port with deep=True) for ComfyUI (/system_stats) and Ollama ("Ollama is
  running" at /: Open WebUI also answers /api/version). On the server itself: process folder, CUDA_VISIBLE_DEVICES, systemd unit, and
  Cloudflare tunnel ingress (marks "published at ...").
- `vt/engines/prepare.py`: plan/prepare/use: download the set's missing files into the instance's own folders (/internal/folder_paths),
  check the graph, save comfy_url + picture_recipe; dead workers dropped. Remote instance + missing files = "install Video Tool's server there".
- `picture_workflow()` (vt/comfy/workflows.py) writes the recipe's loaders into zimage_t2i; reachable() attaches it as client.workflow.
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
  Director prompt (vt/reel/reading.py SYSTEM) teaches it; craft rules picture.place + picture.drawable (measured: no place, no size beside
  something big, negations, similes). Found and fixed literal backspace characters (a mangled `\b`) in craft.py and director/archetypes.py.
- Model bench (scratchpad bench_models.py, 5 hard shots, 3060): Z-Image Turbo 8-bit 21 s/picture; FLUX.2 Klein 4B 9 s/picture, better
  rooms and weather; both 11.5 GB peak; neither draws an upside-down bicycle (hence "close-up of the telling detail"). Qwen-Image 2.1
  Turbo int8 next. Models on the server's SSD (/run/media/roy/OPT/comfyui-models, fstab entry by UUID, nofail; extra_model_paths.yaml
  section fast_ssd, backup .bak-before-ssd); the HDD (5400 rpm) made each first load 5 min.
- Planned (not built): docs/plans/PLAN-CLOUD-AI.MD: OpenRouter key set once and kept in the OS keychain (headless: 600 file), hard budget, cloud director/critic/voice roles with local fallback, and a "collage promo" video type. `.env` added to .gitignore (it held the OpenRouter key, unignored).
- Round 1 done: The Last Lamp with FLUX.2 Klein (places + cast + drawable prompts) → story/one-gpu/the-last-lamp-klein-v2.mp4 (63.6 s; 29
  pictures in 5.9 min). Close-ups now take the place's visible details as a soft background (the place name drew the lighthouse's outside);
  the 9:16 paper-fit picture is 68 % tall so a two-line caption clears it. Left: Mira drawn twice in s21, straight stairs for "winding".
- Picture sets klein-4b (default 12 GB+), klein-4b-fp8, qwen21-turbo, each with its own graph (assets/comfy/workflows/klein_t2i.json,
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
- Sentences: "Mr. Rich" no longer splits (ABBREV in vt/stages/words.py, in both splits). Script voices: `fit_script_words` puts typed words
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
