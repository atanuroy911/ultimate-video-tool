# Documentation: start here

Everything about the project, organised so that an agent or a person can pick it up cold. The product is **0.5 (beta)**.

## Read in this order
| # | Read | For |
|---|---|---|
| 1 | [dev/CODEX-HANDOFF.md](dev/CODEX-HANDOFF.md) and the top of [dev/WORKLOG.md](dev/WORKLOG.md) | how to work here, the owner's rules, and what was done last. Five minutes. |
| 2 | [STATUS.md](STATUS.md) | what is proven, how, and the honest list of gaps |
| 3 | [plans/PLAN-WORKBENCH.MD](plans/PLAN-WORKBENCH.MD) | the step-by-step plan being carried out now (releases, security, tests, the new editor layout, Claude Code inside the app) |
| 4 | [plans/PLAN-PERFECT.MD](plans/PLAN-PERFECT.MD) | the plan for video quality |
| 5 | [ROADMAP.md](ROADMAP.md), [TEST-PLAN.md](TEST-PLAN.md) | the phases, and how everything is tested |
| 6 | [dev/](dev/) | measured baselines, the slow-test table, matrix findings, screenshots |

## Folder map
```
docs/
  README.md        this page
  STATUS.md        what is proven and what is not (short, current)
  ROADMAP.md       the phases
  TEST-PLAN.md     the test layers and the human checklist
  OPEN-QUESTIONS.md  questions held for the owner, and what was decided meanwhile
  GLOSSARY.md      the words used in the product
  DEVELOPMENT-INSTALL.md  running the client and server from source
  dev/             working notes: handoff, worklog, baselines, matrix findings, screenshots
  plans/           the detailed plans (the current ones are PLAN-WORKBENCH and PLAN-PERFECT)
  ops/             the GPU server's runbook (kept for reference)
  research/        what the owner's example reels do, the best models for each job
  history/         earlier plans, audits and the old status ledger, word for word
```
The raw evidence logs (6,556 files) are no longer in the repository: they are in `docs-evidence-2026-11.zip` on the 0.5.0 release.

## Conventions
* A path in `backticks` in STATUS.md or this page **must exist**; the docs are checked: `python scripts/check_docs.py` fails on a broken link, a missing path, a test name not in its file, or a measured number that drifted.
* Paths are relative to the repository root.
