# Documentation: start here

Everything about the project, organised so that an agent or a person can pick it up cold.

## Read in this order
| # | Read | For |
|---|---|---|
| 1 | [HANDOFF.md](HANDOFF.md) | how to work here: commands, rules, the GPU server, traps. Five minutes. |
| 2 | [ROADMAP.md](ROADMAP.md) | **the plan, in phases.** Phase 0 is what exists; **Phase 1 is what to do next**; every phase has tasks with file paths, a gate and the verification commands |
| 3 | [STATUS.md](STATUS.md), and [TEST-PLAN.md](TEST-PLAN.md) for how everything is tested | **what is implemented, where (file paths and functions), the tests, and the logs that prove it**; what is not built; what failed |
| 4 | [plans/](plans/) | the detailed designs behind the phases (below) |
| 5 | [research/REELS-ANALYSIS.md](research/REELS-ANALYSIS.md) | what the owner's high-retention example reels do, measured and watched; the model for Phase 4 |
| 6 | [ops/](ops/), [qa/](qa/), [evidence/](evidence/), [history/](history/) | the server runbook, QA reports, raw test logs, and archived plans |

## Folder map
```
docs/
  README.md        this page
  HANDOFF.md       how to work in the repo
  ROADMAP.md       the master plan: Phase 0 (partly done) ... Phase 10
  STATUS.md        the implementation ledger with evidence
  TEST-PLAN.md     the end-to-end test plan: layers, the automatic battery, the judges, the acceptance corpus, the human checklist
  plans/           detailed designs
    PLAN-DIRECTOR-MODULES.MD      everything is a module; the director, the plan review, the live log (the big one)
    PLAN-AUDIO-FIRST-DIRECTOR.MD  the audio is cut first, cuts land on impact, what fills a slot; the research behind it
    PLAN-COMFYUI-VIDEO.MD         generated clips: the server, the workflows, the measured timings
    PLAN-ENGINES-AND-SETUP.MD     engines (Ollama, ComfyUI, VoiceStudio...) local or remote, the setup wizard, the two-server principle
    PLAN-PACKAGING.MD             the app and the engine as two downloads, the engine hub, the GitHub Actions that build both
    PLAN-VOICESTUDIO.MD           VoiceStudio on the GPU machine and in the app
    PLAN-VOICE-DIRECTION.MD       voice direction and vocal events for the director
    PLAN-REEL-DIRECTOR.MD         the reel director in full: how a script becomes a video that holds attention
    PLAN-EDITOR-UI.MD             the everyday, CapCut-style editor and what is next for it
    PLAN-SHORTS.MD                finding viral moments in long recordings and making shorts
    PLAN-SOCIAL.MD                posting to Meta, YouTube and TikTok with a queue
    README.md                     the plan audit, updated alongside STATUS.md
  ops/             the GPU server's layout, update procedure and rollback
  qa/              QA reports (live scripts, YouTube A-roll, Ollama models, Shorts UI)
  evidence/        raw logs of the test suites and measurements, by date; the code-to-test map; the measured facts
  research/        what the owner's example reels do (REELS-ANALYSIS.md), the best models for each job (BEST-MODELS.md)
  OPEN-QUESTIONS.md  questions held for the end of the build, and what was decided meanwhile
  history/         every earlier plan, word for word (Phases 2-16 and the first rounds)
```

## Conventions
* **Status words:** DONE · PARTLY DONE · NEXT · PLANNED · PARALLEL (phases); ✅ verified · ◐ partial or unmeasured · ✗ not built · ⚠ failing or stale (ledger rows).
* **Paths** are relative to the repository root `C:\Users\atanu\Desktop\Video Tool`. A path in `backticks` in STATUS.md, HANDOFF.md or this page **must exist**; `path::name` must also name something defined in that file. Planned files are written without backticks.
* **Nothing is "done" without a log** in `evidence/`.
* **The docs are checked:** `python scripts/check_docs.py` fails on a broken link, a path that does not exist, a test name that is not in its file, a measured number that drifted, or a roadmap phase without a status.

## When you finish something
1. Update the task and the phase **Status** in [ROADMAP.md](ROADMAP.md).
2. Update the row in [STATUS.md](STATUS.md) (paths, tests, evidence log).
3. `python scripts/collect_evidence.py ...` for the suites you touched; commit nothing without the owner asking.
4. `python scripts/check_docs.py`.
