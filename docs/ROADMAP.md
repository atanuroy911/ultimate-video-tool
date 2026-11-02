# Roadmap: from what exists to the finished product

**Current cross-check (2026-11-03):** [Vision-to-product audit](AUDIT-2026-11-03.md) records the live capability inventory, repaired UI/Director gaps and outstanding acceptance work. Older measurements below remain dated evidence, not current pass claims.

*The master plan, in phases. Phase 0 is what is done; Phase 1 is what to pick up next. Detailed designs live in [plans/](plans/); what exists, where, and the proof for it is in [STATUS.md](STATUS.md). How to work in this repo: [HANDOFF.md](HANDOFF.md).*

**Vision (owner).** Give it a voice (Bangla, English, Banglish), a talking-head video, a long podcast or a link. Get back finished, scroll-stopping videos and an editable timeline, with no human step in between. An AI makes every decision a good editor would, says why, and the person steps in only if they want to.

**The principles every phase obeys** (decided by the owner, 2026-10-26 unless dated otherwise)
1. **The audio is the master and is decided first.** Clean and cut it; a script is spoken one sentence at a time so its real length is known. The picture is derived from the audio, never the other way round.
2. **Cut on impact.** Every change of picture lands on a word or sound that earns it; the goal decides which one. Slots are variable. The first change comes within about 3 seconds.
3. **Everything is a module** the director can call, with declared inputs and outputs; prerequisites run automatically; every call is logged with its reason and can be replayed without an AI.
4. **The director picks the cheapest medium that carries the impact** (speaker, graphic, stock, still with a slow zoom, character scene, and last a 2-4 s silent generated clip).
5. **The person sees the plan before anything expensive runs, and can open a live log** while it works.
6. **AI first, rules as the safety net**: every AI step has a schema, a validator, a cache, a rule fallback and a recorded reason. **Never invent facts**: everything on screen comes from the speaker's words.
7. Something changes on screen at least every 3 seconds, in every shape. Licensing is not a concern. Do not ask; finish the job.

**Status words.** `DONE` built and verified (evidence in STATUS) · `PARTLY DONE` built, with gaps listed · `NEXT` the phase to pick up now · `PLANNED` designed, not started · `PARALLEL` independent of the module work, can be taken at any time.

## The map

| Phase | Name | Status | Needs | Size | Design |
|---|---|---|---|---|---|
| **0** | What exists today | PARTLY DONE | | | [STATUS.md](STATUS.md) |
| **1** | The module runtime, and the pipeline as modules | **DONE** | 0 | M+M | [modules plan](plans/PLAN-DIRECTOR-MODULES.MD) §2, §6 |
| **2** | Every other component as a module | **PARTLY DONE** | 1 | L | modules plan §4, §6 |
| **3** | Surfaces and the live director log | PLANNED | 1 (2 for full coverage) | M | modules plan §3.6, §8.9 |
| **4** | The audio-first modules (impact map, cut plan, ...) | PLANNED | 1 | L | [audio-first plan](plans/PLAN-AUDIO-FIRST-DIRECTOR.MD) |
| **5** | The directors and their evaluation | PLANNED | 2, 4 | L | modules plan §3, audio-first §6 |
| **6** | The plan review | PLANNED | 5 | L | modules plan §8 |
| **7** | Generated clips, wired in | PLANNED | 4, 5 | L | [ComfyUI plan](plans/PLAN-COMFYUI-VIDEO.MD), audio-first §5 |
| **8** | Hardening | PLANNED | 5 | M | modules plan §7 |
| **9** | The director's seat | PLANNED | 6 | M | modules plan §8.13 |
| **10** | Verification and polish of what exists | PARALLEL | 0 | various | [shorts](plans/PLAN-SHORTS.MD), [social](plans/PLAN-SOCIAL.MD), STATUS gaps |

```
 0 ──► 1 ──► 2 ──┬──► 5 ──► 6 ──► 9
        │        │     ▲     │
        ├──► 3   │     │     └──► 7 ◄── 4 (needs 1)
        └──► 4 ──┴─────┘                      8 follows 5
 10 can run at any time, alongside everything
```
Sizes: S about a day, M two to four days, L a week or more of focused work.

---

## Phase 0: What exists today
**Status:** PARTLY DONE · **Detail and proof:** [STATUS.md](STATUS.md) (row ids in brackets)

**Goal.** A working product, built before the module idea: it makes finished videos from a voice, a script or a link in two clicks, with an editor behind it.

| Area | Result | Rows |
|---|---|---|
| Inputs | record, upload, link, typed script spoken by an AI voice; mode detection (talking head, video, audio); automatic language; own-voice cloning | A1-A6 |
| Audio | cleaning, silence and filler cuts, retakes, tightening, hand edits, speech recognition (Bangla fine-tune, Whisper), words and beats, speakers, sound events, stress and arousal measures | B1-B10 |
| Understanding and planning | context reading, rule director, local-model and external-assistant planners, the Video Script director (stick, emoji, cartoon, animals), critic, revise, talk-to-the-director, visual lookup, media bin, stock, AI provider gate, taste | C1-C10 |
| Composition and render | composer and captions, 62 motion recipes mapped to 124 shotcraft cards, layout guard, stick and cartoon engine, speaker's picture with face tracking and a steady pan, layers, render and mix, sound design, retention scorecard and vision QA, publish kit, autopilot with revise loop | D1-D11 |
| Surfaces | the Studio (New, Dashboard, Progress, Result, editor, Settings, Shorts, Social), REST API and jobs, MCP server, Shorts extraction, Social queue, ComfyUI clip generation, packaging | E1-E7 |
| The GPU server | ComfyUI 0.42.5 on a V100-capable PyTorch, Ollama 0.40.11, Open WebUI 0.12.4; runbook and rollback | F1-F3 |
| Tooling | evidence collection, docs checker, code-to-test map, fact counter | G1 |

**Gaps carried forward** (each is a task somewhere below): no module layer (Phase 1); word times for script speech are estimated by letter count (Phase 4); nothing yet decides where generated footage belongs (Phases 4-7); Shorts, tighten and retakes have never been judged on real recordings (Phase 10); live social posting never verified (Phase 10); 11 of 24 browser suites fail, mostly because the screens changed on purpose (STATUS section 6, Phase 10).

---

## Phase 1: The module runtime, and the pipeline as modules
**Status:** DONE · **Needs:** Phase 0 · **Size:** M (the spike) + M (the pipeline) · **Design:** [modules plan](plans/PLAN-DIRECTOR-MODULES.MD) §2 (contracts), §6 phases 0 and 1

**Completed 2026-10-27:** P1-01 through P1-10 are implemented. The three spike modules, registry, typed workspace with versioned JSON, binary and folder undo, executor with prerequisite chaining, cache, budget, ordered resource locks, async JSON tickets and cancellation, events, append-only and redacted logs, replay, CLI, MCP calls and tool-schema export are in place. The twelve `Pipeline.stage_*` adapters and stored `classic` DAG now drive `Pipeline.run`; the stage bodies are unchanged. Byte comparisons pass on the reference project, full Bangla clip and a fixed 20-second excerpt of the English parable. A second run changes no legacy artifact or stage completion time. The final focused suite passed 30 tests, the full fast suite reached 100% with one expected opt-in skip, the full slow suite reached 100%, the isolated Studio flow passed, and registry import measured 57.8-84.6 ms ([Phase 1 evidence](evidence/2026-10-27/phase1.md)).

**Goal.** One contract for "a thing the director can call", proved on three real modules, and then the whole existing pipeline running *through* it with **byte-identical** output, so nothing is lost on the way.

| Task | What | Create or change | Tests to add | Done when |
|---|---|---|---|---|
| P1-01 | Registry: the `@module` decorator, `ModuleSpec` (id, version, summary, when_to_use, inputs, outputs, requires, produces, cost, effects, determinism, grounding, fallback, examples, toolboxes, `plain_name`, `log_line`, `preview`), lint | `vt/modules/__init__.py`, `vt/modules/registry.py` | `tests/test_modules_registry.py` (lint rules, duplicate ids, missing fields) | lint fails on a module without a summary, example, cost or `log_line` |
| P1-02 | Workspace: typed, hashed, versioned artifacts over the project folder (today's file names kept), provenance, staleness graph, last 20 versions | `vt/modules/workspace.py` | `tests/test_modules_workspace.py` | writing an artifact marks dependants stale; undo restores the version |
| P1-03 | Executor: validate inputs, resolve prerequisites (auto or `needs_input`), cache key, budget, resource locks, run, validate outputs, record, emit events | `vt/modules/executor.py`, `envelope.py`, `budget.py`, `resources.py`, `tickets.py` | `tests/test_modules_executor.py` (cache hit, prerequisite chain, budget refusal, lock ordering, async ticket, cancel) | a second identical call is `cached: true` with cost 0 |
| P1-04 | Call log: `calls.jsonl` (seq, level, plain sentence, caller, why, cost), `technical.log` capture with redaction | `vt/modules/calls.py` | `tests/test_modules_calls.py` | every call appears once, in order, with a rendered `log_line` |
| P1-05 | Tool-schema export: Anthropic, OpenAI, Gemini and MCP shapes from one spec | `vt/modules/toolspec.py` | `tests/test_modules_toolspec.py` | the same module validates in all four shapes |
| P1-06 | Three spike modules: `project.inspect_source`, `audio.find_retakes`, `audio.prosody` | `vt/modules/defs/project.py`, `vt/modules/defs/audio.py` | contract tests generated from each module's `examples` | each called through the executor, over MCP, and by `vt call` |
| P1-07 | CLI: `vt modules list`, `vt modules describe <id>`, `vt call <id> --json` | `vt/cli.py` | `tests/test_cli_modules.py` | works on the `reference` project |
| P1-08 | The 12 stages as modules (`voice, preprocess, silence, asr, cuts, sounds, aroll, words, context, tighten, plan, compose`), wrapping `Pipeline.stage_*`; the `classic` recipe (a stored DAG) | `vt/modules/defs/pipeline_stages.py`, `vt/recipes/classic.json`, `vt/modules/recipes.py` | `tests/test_modules_recipes.py` | `Pipeline.run` executes `classic` through the executor |
| P1-09 | **Equivalence**: on three fixed inputs every artifact is byte-identical to today's, and the second run does nothing | `tests/test_modules_equivalence.py` (inputs: the `reference` project, `samples/audio/bn_plain.mp3`, the English parable if present) | itself | hash test green; `pytest -m "not slow"` and `-m slow` unchanged |
| P1-10 | Replay: `vt replay <project>` rebuilds the timeline artifacts from `calls.jsonl` with no AI | `vt/modules/replay.py`, `vt/cli.py` | `tests/test_modules_replay.py` | identical artifacts for `pure` modules |

**Gate.** Lint green; the three spike modules callable three ways; cache hit on the second call; a missing prerequisite returns `needs_input` naming the producing module; **byte-identical** pipeline output on the three inputs; registry import adds under 100 ms (heavy libraries load only on call); all existing tests unchanged.
**Verify.** `python -m pytest -q -m "not slow" tests/test_modules_*.py` then the full fast and slow suites; `python scripts/collect_evidence.py fast`.
**Risks.** The wrapper subtly changing behaviour (hence the byte test first); import cost (lazy imports inside each module).

---

## Phase 2: Every other component as a module
**Status:** DONE · **Needs:** Phase 1 · **Size:** L, in six slices that can run in parallel · **Design:** modules plan §4 (the catalogue) and the appendix (every source file mapped)

**Completed, 2026-10-27:** 125 Phase 2 modules are registered on top of the unchanged implementations (140 modules total including Phase 1). Every existing Phase 0 capability named by slices 2a–2f is callable or explicitly retained as an internal library. The final slice adds creation/link ingestion, transcript correction, face/person/shot and word-visual analysis, all Slot→Fragment fills, final mixing, preview rendering, timeline placement, full-toolbox confirmed social dispatch, unified redo, budget/human/finish controls, audio saliency/alignment, impact-map and cut-plan modules, grounding/alignment judges, and generated-slot orchestration. Registry lint is clean, the 80-case combined module suite and six new completion contracts pass, and the full fast checkpoint completed all 859 selected cases with one expected opt-in skip and zero failures ([Phase 2 core evidence](evidence/2026-10-27/phase2-core.md)).

**Boundary:** `gen.image` and `gen.video_from_text` still require the workflow experiments and assets assigned to Phase 5; `plan.*` review surfaces belong to Phase 4. They are not existing-code adapter gaps and are not counted as Phase 2 work. Real social posting remains an explicit human-confirmed operation and was not exercised by automated tests.

**Goal.** Everything in Phase 0 becomes callable by the director, wrapped, not rewritten. A module is an adapter of about 60 lines with schemas, a description, an example, a measured cost, declared effects, a fallback, and a test that its output equals the wrapped function's.

| Slice | Modules (group.name) | Wraps | Done when |
|---|---|---|---|
| 2a | `project.*`, `audio.*`, `asr.*`, `text.*` (about 57) | `vt/project.py`, `vt/ingest.py`, `vt/source_inspect.py`, `vt/stages/*`, `vt/retakes.py`, `vt/tighten.py`, `vt/audio_edit.py`, `vt/tts.py`, `vt/voices.py`, `vt/sounds.py`, `vt/prosody.py`, `vt/visuals/emphasis.py`, `vt/langdetect.py`, `vt/pausesplit.py`, `vt/transcript_edit.py` | each reachable by `vt call`; equivalence tests green |
| 2b | `understand.*`, `direct.*` (adapters only) | `vt/context.py`, `vt/director/roles.py`, `vt/director/plan.py`, `vt/planner/*`, `vt/script/*`, `vt/ai/*`, `vt/musicpick.py`, `vt/taste.py` | AI-backed modules report their fallback when the AI is unavailable |
| 2c | `fill.*` (Slot in, Fragment out) and `timeline.*` | `vt/director/archetypes.py`, `vt/visuals/*`, `vt/art/*`, `vt/director/stock.py`, `vt/aroll.py`, `vt/script/story.py`, `vt/compose/*`, `vt/scene_ops.py`, `vt/layers.py`, `vt/director/heartbeat.py`, `vt/director/contrast.py`, `vt/thumbs.py` | a fill module returns timeline items only, never anything the renderer alone knows |
| 2d | `sound.*`, `judge.*`, `render.*`, `publish.*` | `vt/cues.py`, `vt/sfxlib.py`, `vt/beatsync.py`, `vt/render/*`, `vt/retention.py`, `vt/ai/vision.py`, `vt/ai/publish.py`, `vt/shorts/*`, `vt/social/core.py` | `publish.dispatch` only in the `full` toolbox |
| 2e | `gen.*` | `vt/comfy/*`, `vt/cutout.py`, `vt/ai/vision.py` | the 10 existing ComfyUI tests move with it |
| 2f | `meta.*` | `vt/doctor.py`, `vt/models.py`, `vt/gpu.py`, `vt/llm.py`, `vt/ai/providers.py` | `meta.catalog` lists every module with a one-line summary |

**Gate (per slice).** Lint green; every file of the slice named in the appendix reachable through a module or listed as a library; equivalence tests against the wrapped function; measured cost within 3x of the estimate; **no change in existing test results**.
**Verify.** `python scripts/map_tests.py` (no module without a test file); `vt modules list --group <g>`.

---

## Phase 3: Surfaces and the live director log
**Status:** DONE · **Needs:** Phase 1 (Phase 2 for full coverage) · **Size:** M · **Design:** modules plan §3.6, §8.9, §8.10

| Task | What | Create or change | Tests | Done when |
|---|---|---|---|---|
| P3-01 | MCP tools generated from the registry; the 31 existing names kept as aliases that call modules | `vt/mcp/server.py` | `tests/test_mcp_aliases.py` (each alias against the old result), existing MCP tests | a stdio client lists and calls modules |
| P3-02 | REST: `/api/modules` (list, describe, call, dry-run) with the same validation | `vt/server/modules_routes.py`, `vt/server/app.py` | `tests/test_modules_api.py` | the Studio can call any module |
| P3-03 | Events: `call` and `ticket` over the WebSocket; log endpoints (`GET /api/projects/{pid}/calls`, one call, cancel, download) | `vt/server/log_routes.py`, `vt/modules/calls.py` | `tests/test_log_api.py` | entries stream in order; download is a zip of both logs |
| P3-04 | The **Details** sheet: hidden by default, opened by a button or `L`; filters (All, Decisions, Problems), search, expandable rows (why, used, result, technical), running rows with progress, *Technical output* switch, download | `studio/src/log/DirectorLog.tsx`, `studio/src/log/LogRow.tsx`, `studio/src/log/TechnicalOutput.tsx`, `studio/src/hooks/useCallLog.ts`, `studio/src/pages/Progress.tsx`, `Result.tsx`, `Review.tsx` | `studio/e2e/log.mjs` | hidden until asked; rows in order; an error row expands to its fix; secrets redacted |
| P3-05 | `technical.log` capture (ffmpeg, ComfyUI messages) bounded to 2,000 lines | `vt/modules/calls.py` | in `test_modules_calls.py` | tail only, redacted |
| P3-06 | **The everyday editor**: a CapCut-style layout for ordinary users (owner, 2026-10-27: "the UI is not user friendly, the timeline feels cluttering"). Built at `/p/:id`; the dense editor moved to `/p/:id/pro` | `studio/src/editor/*`, `studio/src/main.tsx` | `studio/e2e/editor_simple.mjs` | done 2026-10-27; open: edge dragging, music/sound tracks, caption presets (P4-11) |

**Gate.** Codex or Claude Code connected over MCP runs the `classic` recipe by calling modules one at a time and gets the same video; the Studio shows the log live behind its button; the log is complete after a restart.

---

## Phase 4: The audio-first modules
**Status:** PARTLY DONE · **Needs:** Phase 1 · **Size:** L · **Design:** [audio-first plan](plans/PLAN-AUDIO-FIRST-DIRECTOR.MD) §3 to §7

**State on 2026-10-27 (checked, not measured):** Codex registered starter modules for most of this phase: `audio.saliency`, `audio.align_words`, `understand.impact_map`, `cut.propose`, `cut.validate`, `cut.apply`, `cut.snap_quiet`, `direct.set_direction`, `judge.facts`, `judge.impact_alignment` (in `vt/modules/defs/audio_first_new.py`, `vt/modules/defs/cut.py`, `vt/modules/defs/judge.py`, `vt/modules/defs/phase2_remaining.py`) over a 75-line `vt/cutplan.py`. **None of the phase's gates can be claimed:** there is no direction set, no evaluation script and no baseline, so nothing shows the cuts beat today's sentence-based scenes (P4-01 needs the owner's example recordings with an editor's marks, which cannot be invented). The planned files `vt/impact.py`, `vt/saliency_audio.py` and `vt/judge_facts.py`, the `edit_mode: "impact"` option and the still-series fills (P4-08) are not built. Do P4-01 first.

| Task | What | Create or change | Done when |
|---|---|---|---|
| P4-01 | **STARTED 2026-10-28** (the ten reels are measured and the baseline of our two acceptance videos is in [evidence](evidence/2026-10-28/direction-baseline.md); `tests/direction_set/reels.json`; **the 20 recordings with an editor's cuts do not exist**) **The direction set**: about 20 short recordings (English, Bangla; podcast, story, explainer, product) with a human editor's cuts, what each lands on, and the medium; the metrics script and the baseline numbers (today's sentence-based scenes) | `tests/direction_set/` (audio, `marks.json`), `scripts/eval_direction.py` | baseline recorded in `docs/evidence/` |
| P4-02 | `audio.align_words`: measured word onsets for script speech (forced alignment of each spoken sentence); today `tts.word_times` estimates by letter count | `vt/modules/defs/audio.py`, `vt/stages/align.py` | median onset error under 60 ms on 50 hand-marked words |
| P4-03 | `audio.emphasis` upgrade (wavelet prominence behind a `method` input, kept only if it beats `vt/visuals/emphasis.py` on the direction set) and `audio.saliency` (time-only auditory saliency) | `vt/visuals/emphasis.py`, `vt/saliency_audio.py` (new) | agreement with editors measured |
| P4-04 | `understand.impact_map`: stress x goal relevance, sound events, arousal, structure, quiet-and-still; writes `impact.json` | `vt/impact.py` | the editor's cut word is in the top 2 candidates for at least 80 % of sentences |
| P4-05 | `direct.set_direction`: goal, audience, tone, style bible, pacing curve, budget as an artifact | `vt/direction/schema.py` | validates; replays |
| P4-06 | `cut.propose`, `cut.validate`, `cut.apply`, `cut.snap_quiet`, `cut.snap_beat`; option `edit_mode: "impact"` (off by default, bit-identical when off) | `vt/cutplan.py`, `vt/schema.py` | beats the baseline on cut match and hook; property tests hold |
| P4-07 | `judge.facts` (every name, number and claim exists in the speech) and `judge.impact_alignment` (the picture changed within 100 ms of each impact point) | `vt/judge_facts.py`, `vt/retention.py` | invented-fact injection caught |
| P4-08 | `fill.still_zoom`, `fill.placeholder`, `fill.text_card` and the **still-series style** (stills, slow zoom, SVG, text; no animation) | `vt/modules/defs/fill.py`, `vt/compose/composer.py` | three styles produce watchable videos with no generation |
| P4-09 | **PARTLY DONE 2026-10-28** (the reading picks one of four styles and one figure for the whole video; `vt/reel/style.py`; not yet a stored, editable artifact) **Style bible**: one look for the whole video (line art, a named cartoon character, or kinetic type), chosen once by the director and inherited by every image prompt, so all pictures match | [reel analysis](research/REELS-ANALYSIS.md) section 3, pattern 1 | `vt/direction/style.py`; a generated series of 10 pictures looks like one artist made it |
| P4-10 | **DONE 2026-10-28** ([evidence](evidence/2026-10-27/reel-pipeline.md); `vt/reel/`, `vt/comfy/still.py`, `assets/comfy/workflows/zimage_t2i.json`, `tests/test_reel.py`) **A picture drawn for each sentence** (about one per 7 spoken words) with a push-in on every still: `fill.generated_still` through ComfyUI (Z-Image is installed), no video generation needed | pattern 2 and 4 | a 60 s script becomes about 25 pictures that each match their words, none still for more than 3 s |
| P4-11 | **Caption presets**: single huge centre word synced to the voice; the key word grown and coloured; 2 to 4 words with one highlight; an end card ("FOLLOW FOR MORE" or Subscribe) and a day/step counter card | patterns 3, 5, 6 | `vt/compose/composer.py`, `renderer/runtime/vt-motion.js`; the three styles render and are looked at |
| P4-12 | **PARTLY DONE 2026-10-28** (`scripts/eval_direction.py` prints our numbers beside the reels', `tests/test_eval_direction.py`; `tests/direction_set/marks.template.json` waits for the owner's marks: the "which word" test is pending) **Use the reels as the first reference set** for P4-01: seed `tests/direction_set/` with the eight reels' cut times, word times and caption styles from `docs/research/reels/*.json`, and score our output against them on pictures per sentence, words per picture and caption style (not on meaning) | [reel analysis](research/REELS-ANALYSIS.md) section 4 | `scripts/eval_direction.py` prints our numbers beside the reels'; the owner marks the "which word" for two reels to start the impact test |

**Gate.** The audio-first plan's phases 1 to 4. **Verify.** `python scripts/eval_direction.py` and the new tests; the old tests unchanged.

---

## Phase 5: The directors and their evaluation
**Status:** PARTLY DONE (the machinery is built 2026-10-28; **no gate is met**: nothing has been scored on a direction set) · **Needs:** Phases 2 and 4 · **Size:** L · **Design:** modules plan §3, audio-first §6

| Task | What | Create or change |
|---|---|---|
| P5-01 | **PARTLY DONE** (`image-story`, `impact-talkinghead`, `impact-explainer` validate against the catalogue; `autopilot` and `character-story` are not built) L0 recipes as data (`classic`, `autopilot`, `impact-talkinghead`, `impact-explainer`, `image-story`, `character-story`) | `vt/recipes/*.json` |
| P5-02 | **BUILT, not scored** (`vt/direction/plan_director.py`: plan, validator with plain-sentence problems, one repair round, recipe fallback, run with references and checkpoints) L1 plan director: one structured plan (a DAG of module calls with a reason each), dry run, checkpoints, validator, rule fallback | `vt/direction/plan_director.py`, `vt/direction/prompts/` |
| P5-03 | **BUILT, not scored** (`vt/direction/agent.py`: step, time and no-progress caps, a state card under 600 tokens, working set, a scripted-model test, `ollama_step`) L2 agent loop: step, token and cost caps, no-progress detector, a state card of at most 600 tokens, working-set tool schemas | `vt/direction/agent.py` |
| P5-04 | **BUILT** (`vt/direction/prompts/director-v1.md`: eight sections, five worked traces, each checked against the catalogue by `tests/test_direction_agent.py`) The standing prompt (versioned, with five worked traces) and prompt tests | `vt/direction/prompts/director-v1.md` |
| P5-05 | **NOT BUILT** (`scripts/eval_direction.py` measures rhythm of finished videos, it does not run directors on a set) Evaluation harness runs every director and every prompt version on the direction set; scores must not drop | `scripts/eval_direction.py`, `docs/evidence/` |
| P5-06 | External directors over MCP (Claude Code, Codex, Gemini CLI) with the same state card and call log | `vt/mcp/server.py` |
| P5-07 | `autopilot_finish` and `watch_and_revise` become the `autopilot` recipe | `vt/server/app.py` |

**Gate.** On the direction set L1 and L2 beat the baseline on cut match and hook with zero invented facts; a run with a deliberately failing module completes through its fallback; replay reproduces the video with no AI.

---

## Phase 6: The plan review
**Status:** PARTLY DONE (built for reels 2026-10-28, gate not met: no person has reviewed a real plan; not built for classic videos; the plan is written by rules and the reading, not by a Phase 5 director agent) · **Needs:** Phase 5 (not built: see the note) · **Size:** L · **Design:** modules plan §8 (the full specification, wireframes, contracts); [what exists](STATUS.md) row E19

**Goal.** After the quick listening phase the director's plan is shown in plain words and rich detail, editable, and nothing expensive starts until the person presses **Start**; then the same cards become a live board.

| Task | What | Create or change |
|---|---|---|
| P6-01 | `plan.*` modules and the `PlanDoc` contract (`plan.make`, `edit`, `estimate`, `preview_moment`, `approve`, `decline`, `start`, `status`) | `vt/modules/defs/plan.py`, `vt/direction/plan_doc.py` |
| P6-02 | Endpoints: `GET/PUT /api/projects/{pid}/plan`, `POST .../plan/edit`, `.../plan/preview/{moment}`, `.../plan/approve`, `.../plan/decline` | `vt/server/plan_routes.py` |
| P6-03 | The four-step plan sheet: the idea, where the picture changes, what you see in each moment, time and cost then Start | `studio/src/plan/PlanSheet.tsx`, `IdeaStep.tsx`, `ChangesStep.tsx`, `MomentsStep.tsx`, `StartStep.tsx` |
| P6-04 | Moment card, medium picker, word chips, timeline strip, cost meter | `studio/src/plan/MomentCard.tsx`, `MediumPicker.tsx`, `WordChips.tsx`, `TimelineStrip.tsx`, `CostMeter.tsx` |
| P6-05 | The live board after Start (waiting, making, ready, replaced, failed with fallback) | `studio/src/plan/LiveBoard.tsx` |
| P6-06 | Setting `plan_review` (`always`, `when_expensive`, `never`) and a per-video switch on the last New screen; `meta.ask_human(plan_review)` for external directors | `vt/server/app.py`, `studio/src/pages/New.tsx` |

**Gate.** A person reads the plan of a real video, changes a medium, moves a beat, lowers the number of generated clips, sees the time change, presses Start and watches the board fill in; nothing expensive ran before Start; the edits are in the log as the person's calls and survive a replay; `studio/e2e/plan.mjs` passes with screenshots at 1280 and 390 px, light and dark, looked at.

---

## Phase 7: Generated clips, wired in
**Status:** PLANNED · **Needs:** Phases 4 and 5 · **Size:** L · **Design:** [ComfyUI plan](plans/PLAN-COMFYUI-VIDEO.MD), audio-first §5; server facts in [ops/comfyui-server.md](ops/comfyui-server.md)

**What exists** (Phase 0, E6): a still becomes a silent clip on the server (LTX-2.3: about 126 s warm for 3 s vertical; Wan 2.2: about 60 s warm), framed on its subject, kept in the media bin as generated, placeable on the timeline, with captions on top.

| Task | What | Create or change | Done when |
|---|---|---|---|
| P7-01 | `gen.image`: a still from text (Z-Image Turbo is installed on the server) as a third workflow asset | `assets/comfy/workflows/zimage_t2i.json`, `vt/comfy/workflows.py` | a still from a prompt, validated against the live server |
| P7-02 | `direct.write_prompt`: a visual prompt from the speaker's words only, checked by `judge.facts` | `vt/modules/defs/direct.py` | no invented name or number reaches a prompt |
| P7-03 | **Experiment**: direct text-to-video versus still-first on ten prompts (time, vision-model relevance, human judgement); decides whether `gen.video_from_text` is built | `scripts/eval_generation.py`, result in `docs/evidence/` | decision recorded |
| P7-04 | `gen.fit_clip` (trim, or slow up to 20 %, to the slot) and `fill.generated_clip` with placeholders and tickets | `vt/comfy/fit.py`, `vt/modules/defs/fill.py` | a slot of any length gets a fitted clip; export never waits |
| P7-05 | `gen.vision_check`: does the frame show what the sentence says? one retry with a new seed | `vt/ai/vision.py` | a mismatch is retried once, then the fallback medium is used |
| P7-06 | Free ComfyUI's model cache after idle time (it held 39 GB of RAM after two clips) and unload Ollama's models first (already done per call) | `vt/comfy/gpu_share.py`, `vt/server/comfy_routes.py` | the server never fills its memory after a run |
| P7-07 | Frame interpolation so 16 and 25 fps clips do not look steppy at the bin's 30 fps | `vt/comfy/generate.py` | judged by eye on three clips |

**Gate.** Generated clips judged relevant on three real videos; no clip contradicts the speech; a video with the feature off is bit-identical to before.

---

## Phase 8: Hardening
**Status:** PLANNED · **Needs:** Phase 5 · **Size:** M · **Design:** modules plan §7

Concurrency (GPU, comfy and ollama locks under parallel calls), budgets enforced at every level, prompt-injection tests (instructions inside a transcript or a link page are never followed), replay across versions, the module docs page generated from the registry, a call's overhead under 20 ms, a chaos test (kill a module mid-call; the workspace stays consistent). **Gate:** every test class in modules plan §7 exists and passes.

## Phase 9: The director's seat
**Status:** PLANNED · **Needs:** Phase 6 · **Size:** M · **Design:** modules plan §8.13

The module palette (every module in the `studio` toolbox as a form, "the person as director"); the per-item *why* on the timeline with *Ask again* and *Undo this decision*; the plan and the log reachable from the editor. **Gate:** a person re-asks one decision and undoes another, both visible in the log.

---

## Phase 10: Verification and polish of what exists
**Status:** PARALLEL (can start at any time) · **Needs:** Phase 0

These are gaps in Phase 0, independent of the module work. Each has a gate; none should wait for the phases above.

| Id | Task | Why | Gate |
|---|---|---|---|
| P10-01 | **Shorts, measured**: run the podcast sample and three long videos through `/shorts`; a browser suite for the Shorts page | built and unit-tested, never judged against a human's picks | a person agrees with at least 3 of the top 5 picks on 3 videos; no clip starts or ends mid-sentence; each child renders on the speaker's face; `studio/e2e/shorts.mjs` |
| P10-02 | **Retakes and tighten on real recordings** (the M2 gate): five of the owner's phone recordings, Bangla and English | only judged on constructed transcripts | cut vs uncut rated better on all five; no cut mid-word; hook within 1 s |
| P10-03 | **Live social posting**: one real post per platform on the owner's accounts, permalink stored | queue and upload branches tested with mocks only | a permalink per platform |
| P10-04 | **Talking-head polish**: split screen for a wide two-shot; punch-ins on emphasised words; a mode chip on Progress and Result; **cold open** (`Cuts.lead`) | not built | the podcast sample has a person centred in 16/16 frames in all three shapes |
| P10-05 | **Captions for fast narrators** (5-7 words a second): the reading-speed rule exists; check it on real fast speech; emoji in captions | the scorecard counts it against every fast video | reading-speed warnings gone on the parable and the Bangla sample |
| P10-06 | **MOSTLY DONE 2026-10-28** (`editor` 23/23, `dashboard` 10/10, `design` 12/12, `edge` 9/9 pass; `flows`, `phase2`, `timeline`, `link` and `busy` retired with a reason in `studio/e2e/retired/`; `new_flow` replaces the New-page checks; `comfy.mjs` needs the live GPU server and `stick.mjs` a stick-figure project, so neither runs on a scratch Studio (not stale)) **Bring the stale browser suites up to the shipped screens** (the per-suite causes are in [STATUS.md](STATUS.md) section 6): `dashboard`, `editor`, `stick`, `flows`, `design`, `edge`, `busy`, `timeline` | 8 suites assert screens that changed on purpose | every suite passes or is deleted with a reason; rerun `python scripts/collect_evidence.py e2e` |
| P10-07 | **Taste and hook variants**: three hook variants as previews, the scorecard picks; the creator's undos become preferences | designed, not built | the second video of a creator needs fewer edits than the first |
| P10-08 | **Product**: sign the installer; logos and flags for named things; CapCut and JianYing draft export; more cartoon characters (adults) | unsigned, Windows only | an installer that runs on a clean machine |
| P10-09 | **Server hygiene:** redundant model copy deleted after owner approval and a SHA-256 verified big-disk copy ([evidence](evidence/2026-10-26/comfy-model-cleanup.md)); backup pruning and the old Open WebUI container decision remain | root gained 124.6 GB and is below 70 % used | assess backups and old container separately |
| P10-10 | **DONE 2026-10-28** (the `docs` job of `.github/workflows/ci.yml` runs the checker on every push and pull request; not yet run on GitHub) **Docs and evidence upkeep**: after any change run `python scripts/check_docs.py` and refresh evidence | the docs must not rot | the checker passes in CI |
| P10-11 | **DONE 2026-10-28** (`studio/e2e/new_flow.mjs`: Fine tuning has *Kind of video*, a link shows the rights note, a script is shown large while recording) **Restore what the New flow dropped**: the *Kind of video* picker (a Fine tuning row, `/api/usecases`), the *free to reuse* rights note on the link group, the *script prompter* for recording | found by the `phase2` and `link` suites (now retired: `studio/e2e/retired/`); verified absent in `studio/src/pages/New.tsx` | the three are back in the New flow and `studio/e2e/new_flow.mjs` asserts each of them |
| P10-12 | **Find out why `crawl` takes over 10 minutes** (hung, or only slow with the larger Studio?) | timed out at 600 s on 2026-10-26 | the crawler finishes, or the page it stops on is fixed |
| P10-13 | **Put the project under version control** (there is no `.git`; every change so far could not be undone except by hand). Needs the owner's say-so on what to commit | the earlier sessions lost nothing only because edits were small | a repository with a first commit and a `.gitignore` that keeps `projects/`, `models/`, `qa_*`, `dist/` out |
| P10-14 | **DONE 2026-10-28** (`tests/test_untested_four.py`, 13 tests; the [map](evidence/code-test-map.md) lists each with a test) Tests for the four files nothing touches (`vt/doctor.py`, `vt/visuals/icons.py`, `vt/visuals/terms.py`, `vt/shorts/prompts.py`) | `docs/evidence/code-test-map.md` | each has a test; the map shows none untested |
| P10-15 | **Find out why the GPU server failed on 2026-10-27** (it recovered after a restart; the root disk was renumbered `sda` to `sdd`): `dmesg`, `smartctl` on the disks, and whether `/usr/share/ollama` sat on a failing drive; keep a note in [ops/comfyui-server.md](ops/comfyui-server.md) | [probe](evidence/2026-10-27/gpu-server-probe.md), [re-check](evidence/2026-10-27/gpu-server-recheck.md) | the cause is written down, or the disk is replaced |
| P10-16 | **The script AI must clear its own eval**: it won 5 of 10 sets and the test needs 6. Look at the 4 ties (the AI equals the rules, so nothing is gained) and the `product-bike` loss; decide whether to improve the prompt or change the bar and say why | [log](evidence/2026-10-27/ollama-script-eval.log) | `VT_EVAL_MODEL=1 pytest tests/script_eval -k real_model` passes, or the bar is changed in writing |
| P10-17 | **Whole-build acceptance, after Phases 4 to 8**: make 10 real videos end to end (English and Bangla; script, voice and link; with and without generated clips) with the Studio's defaults and the director in charge, and have a person watch each one against a written checklist: does the picture match the sentence, does it change on the right word, is every claim in the speech, does anything look broken, would you post it | the owner's request of 2026-10-27: finish the build, then test that the final video makes sense | a table of 10 videos with the checklist filled in and the failures turned into tasks |

---

## How to update this file
When a task finishes: change its row to done (or delete it and add a line under that phase's *Done*), update the phase **Status**, update the matching row in [STATUS.md](STATUS.md) with the evidence log, and run `python scripts/check_docs.py`. Never mark something `DONE` without a log in `docs/evidence/`.

---

## Phase 11: Engines, voices and the setup
**Status:** PARTLY DONE (2026-10-28) · **Needs:** Phase 1 · **Size:** L · **Design:** [engines and setup](plans/PLAN-ENGINES-AND-SETUP.MD), [VoiceStudio](plans/PLAN-VOICESTUDIO.MD), [voice direction](plans/PLAN-VOICE-DIRECTION.MD), [best models](research/BEST-MODELS.md)

The owner's vision: a **standalone** app whose setup downloads what it needs and also asks "do you run these elsewhere?"; engines (Ollama, ComfyUI, VoiceStudio, others) are local or remote and interchangeable; our own models can be packaged as a server; **the pipeline depends on ComfyUI and Ollama only**; the best model for each job; voice **direction** and **vocal events** available to the director.

| Task | What | State | Where / evidence |
|---|---|---|---|
| E0 | Engine registry: spec, endpoint (mode, url, key, workers), health, settings migration from `ollama_url` and `comfy_url`, `/api/engines` | **DONE** | `vt/engines/`, `vt/server/engines_routes.py`, `tests/test_voicestudio.py` |
| E1 | Settings, Engines page in the Studio (cards, a Step 1-2-3 sheet, test in words, workers); the top-bar chip | **DONE** (the chip is not) | `studio/src/pages/Engines.tsx`, `studio/e2e/engines.mjs` |
| E2 | VoiceStudio as an engine: client, the `voicestudio` voice, speech and model install | **DONE** (speech proven with KittenTTS; the default model is accepted and installed) | `vt/voicestudio/`, `vt/tts.py::_synth_voicestudio`, [evidence](evidence/2026-10-28/voicestudio-install.md) |
| E3 | Models and recovery: manifests, `scripts/voicestudio_models.py`, runbooks | PARTLY DONE (VoiceStudio and ComfyUI voice nodes; `vt models move` not built) | [ops/voicestudio-server.md](ops/voicestudio-server.md), [ops/comfyui-voice-nodes.md](ops/comfyui-voice-nodes.md) |
| E4 | The setup wizard (7 steps, resumable, English and Bangla) | PLANNED | plan section 3.2 |
| E5 | Local installers (Ollama, ComfyUI managed, VoiceStudio, Whisper) | PLANNED | plan section 3.3 |
| E6 | Engine Server: `vt serve-engine`, pairing, "Engine only" package | PLANNED | plan section 3.4 |
| E7 | Modules resolve capabilities to engines; per-engine locks; the engine named in every log row | PLANNED | plan section 3.1 |
| V0 | VoiceStudio on the GPU machine (RTX 3060, data on the big drive), LAN API, `voice.atanusroy.com` | **DONE** | [evidence](evidence/2026-10-28/voicestudio-install.md) |
| VC-1 | **Voices through ComfyUI**: workflow kind `audio`, `vt/comfy/voice.py`, `vt/comfy/voicing.py`, the `comfyvoice` engine, workers, Breeze workflows | **DONE in the app, tested against a fake server** | `tests/test_comfy_voice.py` |
| VC-2 | **Install the node packs on the GPU server and run one real sentence per workflow**; write the OmniVoice workflows from the real node ids; set `status: verified` | **DONE 2026-10-28** (all five workflows verified; a reel voiced by Breeze) | [evidence](evidence/2026-10-28/voices-comfyui.md) |
| VD-1 to VD-6 | Voice direction and events: parsing, per-engine dialects, the director's suggestions, option `voice_direction` | parsing, dialects, suggestions, option **DONE**; VD-1 timing of events, VD-2 editor, VD-3 New flow (**the *Delivery* switch is in the voice screen since 2026-10-28**: directed or plain; the per-sound controls are not), VD-4 voice cast, VD-5 listening test, VD-6 Chinese **PLANNED** | [plan section 5](plans/PLAN-VOICE-DIRECTION.MD), `tests/test_voice_direction.py` |
| V3 | Native Voices page and Settings -> Voice; "Open the full VoiceStudio" frame | PLANNED | [PLAN-VOICESTUDIO.MD](plans/PLAN-VOICESTUDIO.MD) section 3 |
| V5 | Dubbing and long-form (audiobook) | PLANNED | same |
| B-1 | The best model for each job, written down and revisited when a better one appears | **DONE (first pass)** | [research/BEST-MODELS.md](research/BEST-MODELS.md) |

**Gate.** A clean machine with only ComfyUI and Ollama makes a voiced reel (English with direction, and Bangla) end to end; the wizard connects a second computer's engines; switching an engine from remote to local changes nothing else.

---

## Phase 12: The reel director, the everyday editor, and the test battery
**Status:** PARTLY DONE (2026-10-28: see [AUDIT-2026-10-28.md](AUDIT-2026-10-28.md) for what is truly done; most tasks here are built only in part) · **Needs:** Phases 3 and 11 · **Size:** L · **Design:** [reel director](plans/PLAN-REEL-DIRECTOR.MD), [editor UI](plans/PLAN-EDITOR-UI.MD), [test plan](TEST-PLAN.md)

The first version of each runs today (a script becomes a voiced, illustrated, captioned video through the real servers; the Studio has a CapCut-style editor; the Details log is live). This phase finishes them. The task tables are in the three design pages; this page only keeps the order.

| Order | Tasks | Why this order |
|---|---|---|
| 1 | **T-1** the automatic battery `scripts/run_all_checks.py` (built 2026-10-28), **T-4** the judges (first frame, nothing still, change on the word, facts, loudness, glitches) | every later change is then measured |
| 2 | **R1** register the reel stages as modules, **R3** caption presets, **R4** hook and end card, **R14** measure against the nine reels | the video the owner sees gets better first |
| 3 | **T-2** the acceptance corpus A1 to A10, **T-3** the human checklist in the Result page | "does the video make sense" becomes a routine |
| 4 | **R2** style bible, **R6** a consistent figure, **R7** budgeted clips, **R9** voice cast, **R5** fact cards | quality of the pictures |
| 5 | **U1 to U5** editor edge drag, audio tracks, caption styles, per-sentence voice, replace a picture | the editor catches up with the director |
| 6 | **R10, R11** long form and Bangla end to end, **R8** hook proposals, **U6** the plan sheet, **R12, R13** | the long and the non-English cases |
| 7 | **T-5, T-6** non-functional and clean-machine tests, **E4 to E7** the wizard, installers and Engine Server | release |

**Gate.** The battery is green with `--slow --e2e --live --reel`; A1 to A10 are accepted by a person; the clean-machine list passes on two machines; the owner makes a video from a script and a voice recording without help.
