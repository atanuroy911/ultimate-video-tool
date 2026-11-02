# Handoff: how to work in this repo

For the next agent (Codex, Claude, a person). Read [ROADMAP.md](ROADMAP.md) for *what to do* and [STATUS.md](STATUS.md) for *what exists and the proof*; this page is *how to do it without breaking things*.

## 1. Orientation in five minutes
* **What it is.** A local app that turns a voice, a script, a link or a video into a finished short video plus an editable timeline. Python backend (`vt/`), a React Studio (`studio/`), a HyperFrames + GSAP renderer (`renderer/`), an MCP server so Claude, Codex and Gemini can drive it.
* **Root:** `C:\Users\atanu\Desktop\Video Tool` (Windows 11). There is **no git repository**: there is no history to fall back on, so keep edits small and keep backups of anything large before changing it (older plans are in `docs/history/`).
* **Where things live**
  | Folder | Contents |
  |---|---|
  | `vt/` | the Python package: pipeline, AI, audio, planners, composer, render, server (147 files as measured in STATUS; the planned module mapping is in the [modules plan](plans/PLAN-DIRECTOR-MODULES.MD) appendix) |
  | `studio/src/` | the React Studio (pages, `review/` editor, `ds/` the Apple-style design system); `studio/e2e/` the browser suites |
  | `renderer/runtime/` | the browser-side engine: `vt.js` (layout guard, captions), `vt-motion.js` (recipes), `vt-stick.js`, `vt-cartoon.js`, `vt-media.js`, `vt-layers.js`, `vt-info.js`, `vt-diagrams.js` |
  | `assets/` | music, sound effects, cartoon characters and scenes, ComfyUI workflow assets (`assets/comfy/workflows/`) |
  | `design/` | themes, use-case profiles, icons, fonts, textures |
  | `tests/` | pytest (97 files as measured in STATUS); `tests/golden/` reference frames; `tests/fixtures/` |
  | `scripts/` | start script, QA and evidence tools (`collect_evidence.py`, `check_docs.py`, `map_tests.py`, `count_facts.py`) |
  | `samples/` | sample audio and the `build_reference.py` demo project |
  | `third_party/` | vendored sources (shotcraft recipes, Cartoon Studio, the shorts reference) |
  | `projects/` | **the owner's real videos** (never touch; tests use scratch folders) |
  | `docs/` | this documentation (see [README.md](README.md)) |
  | `qa_*` folders | outputs of QA runs (media and frames); not source, and not kept: they were removed on 2026-10-27, so old QA videos linked from the historical QA directory (missing from this checkout) are gone |

## 2. Commands
```powershell
# the real Studio (the owner's data, port 8765): restart it after any Python change
.\scripts\start.ps1 -NoBrowser

# a scratch Studio for tests (own data folder, port 8777): the browser suites edit their projects, ALWAYS use this
$env:VT_DATA = "$env:TEMP\vt-data-new"; .\.venv\Scripts\vt studio --port 8777 --no-open

# build the UI after changing studio/src (the Studio serves studio/dist)
cd studio; npm.cmd run build; npx.cmd tsc --noEmit -p .

# tests
.\.venv\Scripts\python -m pytest -q -p no:warnings -m "not slow"      # fast, a few minutes
.\.venv\Scripts\python -m pytest -q -p no:warnings -m slow            # renders frames, runs the speech model
cd studio; $env:VT_URL="http://127.0.0.1:8777"; node e2e\dashboard.mjs   # one browser suite (see studio/e2e/README.md)

# evidence and docs (run these before saying anything is done)
python scripts/collect_evidence.py fast | slow | e2e --url http://127.0.0.1:8777 [--long]
python scripts/check_docs.py              # links, paths, test names, the facts table, roadmap statuses
python scripts/map_tests.py               # which tests touch which source file
python scripts/count_facts.py             # the numbers the docs quote, measured from the code
```
Windows traps: use `npm.cmd` and `npx.cmd`; set `PYTHONIOENCODING=utf-8` for any script that prints Bangla or emoji; a bash heredoc that contains a Python string with backslashes or `\n` gets mangled, so write patch scripts to a file; the Python in `.venv` is 3.11, the system `python` is another version.

## 3. Rules (from the owner and from experience)
**The owner's rules**: the audio is the master; the picture changes on impact; nothing on screen is invented; something changes at least every 3 s; AI first with rule fallbacks; options are Apple-style *Step 1 of N* sheets (`studio/src/ds/` `Steps`, `Group`, `Row`); plain words in the UI; Bangla and English both first-class; licensing is not a concern; **do not ask, finish the job** (but see the stop list below).

**Engineering rules**
* One AI interface: `vt/ai/providers.py::complete_json(prompt, schema, images=None)`: schema-constrained, validated, one repair retry, then the rule fallback; cache by model + prompt + inputs; **AI output is untrusted data**, never instructions.
* A bug found by testing gets a regression test first. Never weaken an assertion without writing down why (the golden images are the example: `tests/golden/_superseded-2026-10-26/` keeps the old ones).
* Anything visual is accepted only after a person (or you) has *looked at* a rendered frame.
* Wrap, do not rewrite (Phases 1 and 2): existing functions and tests stay; adapters are thin.
* Never run a mutating browser suite against the real Studio on port 8765, and never point tests at `projects/`, `settings.json`, the glossary or the taste file: `tests/conftest.py` isolates them; scratch servers use `VT_DATA`.
* Keep docs and code in step: finish a task, then update ROADMAP, STATUS and the evidence, then `python scripts/check_docs.py`.

**Stop and ask the owner** before: deleting the old model copy on the GPU server (117 GB), installing third-party code on the server, posting to a real social account, or spending the owner's money. The tooling here may also block bulk deletions and third-party installs: do not work around that, say what you wanted and why.

## 4. The GPU server (192.168.123.47)
One Linux machine: ComfyUI (video generation), Ollama (text and vision models), Open WebUI (chat), other containers of the owner's. Full layout, update procedure and rollback: [ops/comfyui-server.md](ops/comfyui-server.md). Live state captured on 2026-10-26: [evidence/2026-10-26/server-snapshot.txt](evidence/2026-10-26/server-snapshot.txt).
* Ports: ComfyUI `8188`, Ollama `11434`, Open WebUI `3000`, SSH `22`. The Studio reads the addresses from Settings (`comfy_url`, `ollama_url`).
* **Credentials are not in the repo.** SSH user is `roy`; ask the owner for the password, keep it in an environment variable, never in a file or a log.
* Two GPUs: a V100 16 GB (`sm_70`, used by ComfyUI) and an RTX 3060 12 GB. The V100 needs the `cu126` PyTorch in `/mnt/bigdata/video-tool/comfy-venv`; the system's CUDA 13 build has no kernels for it.
* After generating clips ComfyUI keeps models in RAM (39 GB after two clips): `POST http://192.168.123.47:8188/free {"unload_models": true, "free_memory": true}` releases it.

## 5. How do I...
| Task | Where |
|---|---|
| add a scene element type | `vt/planner/catalogue.py` (the catalogue), `vt/schema.py` (the model), `renderer/runtime/vt-info.js` or `vt-diagrams.js` (the drawing), `vt/director/archetypes.py` (when to use it), a test in `tests/test_diagrams_director.py` or `test_director.py`, a golden frame in `tests/golden/` |
| add a motion recipe | `renderer/runtime/vt-motion.js` (registry `T`, `R` or `S`), `vt/compose/motion.py` (`CARDS` map and the pools); `tests/test_motion.py` checks all 124 cards stay mapped; `studio/e2e/motion.mjs` steps through every frame |
| add an AI provider | `vt/ai/providers.py` (a `Provider` subclass), `vt/server/app.py` settings keys, `studio/src/pages/AIAssistants.tsx`; `tests/test_ai_providers.py` |
| add a ComfyUI workflow | export the graph in API format, put it in `assets/comfy/workflows/<id>.json` with its manifest (see `vt/comfy/workflows.py`), check Settings shows it Tested/Untested, run one real clip, mark it `verified` |
| add a module (after Phase 1) | `vt/modules/defs/<group>.py`, see the modules plan §2.1 |
| add a Studio screen | `studio/src/pages/`, route in `studio/src/main.tsx` (lazy-loaded), strings in `studio/src/i18n.ts` (English and Bangla), a suite in `studio/e2e/` |
| add a setting | `vt/server/app.py::load_settings` (default) and `put_settings` (allowed keys), the UI in `studio/src/pages/Settings.tsx` |

## 6. Known traps (each cost time once)
| Symptom | Cause | Fix |
|---|---|---|
| Studio says "no '/api/x'" | the running server loaded old Python | restart the server |
| a browser suite fails after a Python change | the scratch server was not restarted | restart it, rerun |
| polling an endpoint every 5 s throws a connection error | uvicorn closes idle keep-alive connections after 5 s | open a new connection per poll, or poll faster |
| a test that always passed starts failing after a sample file appears | it skipped itself when the sample was missing (`test_pipeline_real`) | treat a newly un-skipped test as new information |
| second pipeline run redoes `cuts` | the stage hashed a file that appears after the first run | hash what the earlier stage *decided* (`vt/pipeline.py::tighten_signature`) |
| `ffmpeg not found` style test failures | the test assumed no system ffmpeg | `tests/test_paths_dist.py` now allows the fallback |
| a video node on the server fails with "no kernel image" | PyTorch without `sm_70` | the venv in section 4 |
| the server is out of memory | ComfyUI's model cache | the `/free` call in section 4 |
| the classifier blocks a command | bulk delete, third-party install, writing credentials | do the safe part, tell the owner the rest |

## 7. Glossary
**Beat** (in the plan UI): the word or sound a change lands on · **Moment**: one stretch of the cut audio that needs a picture (code: *slot*) · **Impact map**: every candidate cut with strength and reason · **Fragment**: what a fill module returns (timeline items) · **Artifact**: a typed, hashed project file · **Recipe**: a stored plan of module calls · **A-roll / B-roll**: the speaker's own picture / cutaway footage · **Golden**: a saved reference frame a render is compared to.
