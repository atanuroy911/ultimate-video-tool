# Work log

Newest first. Every agent (Claude Code, Codex) adds an entry when it stops: what it did, what it verified, what is left. Read
`CODEX-HANDOFF.md` first.

## 2026-11-02 (Codex) — director choice (in progress)

**Plan:** Build the director registry and fallback selection as one shared `vt/` capability, expose it through `/api/directors`, project
creation, CLI, MCP, and the Studio New/Settings flows, then connect the desktop WebSocket client so a logged-in local Claude can answer a
remote server's directing request with Video Tool MCP tools only. Verify registry/selection, fake-device completion, timeout fallback, and
tool allowlisting with focused tests; then typecheck/build Studio, run the related suite and full pytest, restart the lab Studio, and make
and judge the billionaire comparison through the real UI and GPU path.

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
