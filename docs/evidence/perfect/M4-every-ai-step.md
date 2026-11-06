# M4: every AI step of a video goes to the person's director

## What changed
- `directors.py`: `DirectorBroker.ask(...)` (blocking, like `request`), `ready()`, `who_directing()`, a cancel sent to the helper when the server stops waiting, `director_model` (default `sonnet`, only letters/digits/dots/dashes) in `settings()` and sent with both `direct` and `ask`. One conversation name, `claude-pc` / `codex-pc`, for the broker's own rows, the question rows and the tool rows (`who_directing` names the tools a director calls during its session; before, they were all "assistant"). The "not ready" note now names the right program for Codex.
- `ai/providers.py`: `ClientProvider` (images, `available()`, plain failure reasons for limit / sign-in / timeout), `provider_for(chosen)` as the one place that maps a director id to its AI, `Provider.why_not()`. `NoProvider` and its `isinstance` checks are gone.
- `pipeline.py`: `_director_provider` uses `provider_for`; `stage_compose` now runs the last look for these videos too; new `directing(project)` scope.
- `server/jobs.py`: every job that asks an AI about a video (`media plan qa autofix director polish context publish scene-direction redraw shorts`) runs inside `directing(project)`. Before, a manual "check the frames" or "write the publishing text" used the global AI setting and wrote nothing on the video's record.
- `server/app.py`: `ask_done` is handled in the `/ws` loop; results are accepted only from the device the task went to.
- `server/plan_routes.py`: the reel plan chat ("the director turns a sentence into plan operations") asks the video's own director.
- Studio `AiTalk.tsx`: "Claude on this PC" / "Codex on this PC".
- `tests/conftest.py`: each test gets an empty AI answer cache. The repo's ignored `ai_cache/` folder had 77 saved answers that tests were reading and adding to, so a second run could behave differently from the first.

## Audit: what reaches the local AI without the provider
| Place | Reaches Ollama directly? | Runs for a client-directed video? |
|---|---|---|
| `planner/llm_plan.py` (`story_brief`, `plan_llm`) | yes (`llm.chat_json`) | no: only `stage_plan` when the director is `local` |
| `reel/plan.py:133` | `llm.release()` only | no AI call |
| `ai/vision.py:285` | imports a helper, `judge_picture` goes through the provider | follows the scope |
| `modules/defs/meta.py:76`, `server/app.py:654-681`, `engines/*`, `setup_routes.py` | status and set-up routes | not part of a video |
| `direction/editor.py::propose` (per-scene rebuild) | `director: "configured"` uses the global AI setting | **gap, kept**: not changed here |
| `reel_routes.py:152` first-line rewrites | uses the global AI setting, but runs on a script before any video exists | no director yet |

## Checks
- `tests/test_one_director.py`: 9 new/changed tests. A video directed by `claude@laptop` sends understanding, planning (the `direct` session), the last look (with pictures) and the title to the stand-in computer; a guard fails the test if `OllamaProvider.complete`, `ClaudeCLIProvider.complete` or `llm.chat_json` is ever reached; every conversation row says `claude-pc`, including the tool row. Others: plain failure wording, the model setting, cancel on timeout, `who_directing`, the job scope, the plan chat, a real `/ws` round trip with a wrong-device answer refused.
- Six deliberate breakages are each caught by a test: no client provider, jobs outside the scope, no cancel, generic tool-row name, model hard-wired in `ask`, model left out of `direct`.
- Local: 92 passed, 1 skipped across the director/provider/job test files, plus 136 passed in the API/plan/script/module files. On the GPU server (CPU-only files, uptime unchanged afterwards): 110 passed, 1 skipped.

## Kept for later steps
- The per-scene frame check (`vision.qa_project`) asks once per scene, up to 20, so a client-directed video spends a few minutes more on the last look than before.
- `direction/editor.py::propose` with "configured" still uses the global AI.
