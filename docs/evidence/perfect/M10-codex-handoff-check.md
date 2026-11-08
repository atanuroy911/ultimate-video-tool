# M10 handoff follow-up — implementation Done by codex

2026-11-07. Followed item 2.1 in `docs/plans/CODEX-NEXT-STEPS.md` from the tree containing Claude's latest edits at `c807fb7` plus working-tree changes.

The existing server project's AI conversations were read through its GET endpoint. `2026-11-07-m10c-sonnet` started its Claude directing task at 13:46:51, reached the 120-second timeout at 13:48:51, then recorded two Ollama planning calls. It requested the full script brief twice. Each stored response was about 63,000 characters, with about 33,000 characters in the task text. A `get_current_script` request got the expected no-script exception. No `submit_script` row appears in the record. The old logger did not record tool calls whose project argument was named `project_id`, so the absence of a `module_call` conversation row cannot distinguish a stall there from time spent writing the script. The terminal output file from the handoff was unavailable.

The scoped Sonnet/Codex task now starts with one concise script brief and asks for `submit_script` before frame review. It keeps every timed word, the full schema, craft rules, style, visual choices, and examples for frequently used elements. Longer worked examples and the craft report on the rule draft stay in the full brief for ordinary MCP assistants. A scoped request for a nonexistent current script returns the next action instead of throwing. The direct prompt uses the registered `module_call` name for `craft.check` and requests one look and one revision.

Within a scoped director task, modules that would delegate the director's work back to a model return an immediate refusal with the corresponding project tool or direct action. The catalogue and module description expose that guidance. The existing provider-level guard remains in place for other code paths. Ordinary assistant sessions retain module access. `module_call` now records the project conversation using its `project_id` argument, including refusals and successful checks.

Local verification after the edits:

```text
cd server
..\.venv\Scripts\python.exe -X utf8 -m pytest -q -c NUL --rootdir=.. ..\tests\test_mcp_scope.py ..\tests\test_director_choice.py ..\tests\test_codex_path.py ..\tests\test_script.py::test_prompt_contains_all_parts ..\tests\test_director_authority.py::test_a_director_is_never_asked_to_do_a_step_inside_its_own_task
43 passed, 6 existing FastAPI lifecycle warnings
```

The scoped test verifies a task body under 70% of the full fixture brief, identical schema and timed transcript, immediate refusal before the executor, allowed `craft.check`, visible conversation records, and unaffected ordinary module calls. The selection also exercises the real MCP protocol with an in-process fake device. The existing remote video is a failed M10 attempt. The local changes await deployment and a fresh successful Sonnet acceptance run. M10 and its dependent real-video checks remain open while renders are paused.
