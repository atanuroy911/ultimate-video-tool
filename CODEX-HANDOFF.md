# Handoff for Codex (and any other agent)

The owner works with Claude Code and Codex interchangeably. Read this file first, then the tail of `WORKLOG.md` (newest entries at the
bottom) for details of what was done. When you stop, update both: what you did, what you verified, what is left.

## The product in one paragraph

Video Tool turns a typed script, a voice recording or a link into a faceless short video. Retention is the metric: every change should make
people watch longer. The parts:
- `vt/`: Python package (FastAPI server, pipeline, director, renderer driver, MCP).
- `renderer/`: HyperFrames HTML/GSAP compositions rendered by Chrome.
- `studio/`: React web UI, served by the server.
- `desktop/`: Electron shell.

Engines: Ollama (the local AI), ComfyUI (pictures, clips, some voices), Edge TTS / other voices.

## The owner's standing rules (do not break)

1. **UI wraps everything.** Users never run commands after install. Every capability is one function in `vt/`, exposed as an `/api`
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
- Our server install: `/mnt/bigdata/video-tool-server/app` (a copy of `vt/`; sync with a tarball through `put.py`). Never touch
  `/mnt/bigdata/video-tool` except the model folders.

**This PC's settings:** Ollama `http://192.168.123.47:11434`, ComfyUI `http://192.168.123.47:8188`, `picture_recipe=klein-4b`.

## Where things are

| Area | Files |
|---|---|
| Client/server, pairing, MCP bridge | `docs/plans/PLAN-CLIENT-SERVER.MD`, `vt/server/serve.py`, `vt/server/clients.py`, `vt/server/discovery.py`, `desktop/` |
| Find/choose a ComfyUI, VRAM fit, picture sets | `vt/engines/discover.py`, `fit.py`, `prepare.py`; `vt engine find / use`; Studio `components/FindEngines.tsx`; `/api/discover` |
| Picture graphs | `assets/comfy/workflows/klein_t2i.json` (default), `qwen21_t2i.json`, `zimage_t2i.json`; `vt/comfy/workflows.py picture_workflow()` |
| Reel director (pictures per moment) | `vt/reel/reading.py` (the local AI director's prompt), `vt/reel/plan.py`, `vt/reel/style.py` (`prompt_for`, `cast_for`) |
| Plan document (places, cast, moments) | `vt/direction/plan_doc.py` (ops `set_place`, `set_moment_place`, `set_cast`, `set_prompt`, `merge`, `set_medium`, …) |
| Craft rules and checks | `vt/craft.py`: areas `script`, `hook`, `sync` (`picture.place`, `picture.drawable`), `pacing`, `captions`… |
| Hand-back (text leaves the picture) | `vt/compose/composer.py` (`until`, `_hand_cards_back`), `renderer/runtime/vt.js`, `vt-media.js`; `tests/test_handback.py` |
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
2. **Build it everywhere it belongs.** One function in `vt/`, then:
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
2. **Natural, expressive narration for every video (owner, 2026-11-02: "natural voice with tones and ups and downs").**

   Today English uses Edge TTS: clean but flat, because its free endpoint only changes speed. The parts for expression exist but are not
   on by default:
   - `vt/voice_direction.py`: per-sentence delivery notes `{...}` and sounds `(laugh)`; `suggest()` lets the director write notes.
   - Breeze TTS 2 on ComfyUI 8188 (`assets/comfy/workflows/breeze_direction.json`, `breeze_design.json`, verified on the 3060 on Oct 28).
   - The one-narrator lock (`vt/voice_lock.py`).

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
   - Full pytest. Known failure: `tests/test_music_auto.py::test_mood_picks_a_fitting_track_stably` expects hiphop, gets upbeat.
   - Remove the 64 `design/themes/auto-*` folders left by old projects.
   - The gemma4 context step (~150 s), post-plan QA time (~6 min), Studio timeline smoothness.
10. **Not before the owner says:** `docs/plans/PLAN-CLOUD-AI.MD` (OpenRouter key kept in the OS keychain, budget, cloud director/critic,
   collage promo video type). Plan only.

## Known problems and traps

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
- Script voices' word times drift. `fit_script_words` (`vt/stages/align.py`) puts typed words back on the speech; never let a typed word
  be dropped.
- Abbreviations ("Mr.") must not end sentences or caption lines: `ABBREV` in `vt/stages/words.py`.

**The local AI director (gemma4):** it still writes "a figure" in some shots. A cast fallback figure then appears and confuses the
story. Consider having the reel director refuse a shot without a named person when the plan has a cast.
