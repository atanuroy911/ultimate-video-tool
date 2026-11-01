# Phase 1 module runtime and classic recipe evidence

Date: 2026-10-27. All project tests used pytest scratch directories under `qa_phase1`; no owner project was edited.

## Byte comparison

`tests/test_modules_equivalence.py` runs the former `Pipeline.run` stage loop as a test oracle, saves SHA-256 hashes of every legacy project file, restores the same starting project at the same absolute path, and runs the new `classic` recipe. Executor sidecars (`calls.jsonl`, `artifacts.json`, module cache and history) are excluded because they have no legacy counterpart. The test also runs the recipe a second time and checks all legacy hashes and stage completion times remain unchanged. Wall-clock fields are fixed in the test so a timestamp does not masquerade as a behavior difference.

| Input | Scope | Result | Log |
|---|---|---|---|
| `reference` fixture | manual transcript, plan and both composition shapes | byte-identical | [equivalence-reference.log](equivalence-reference.log) |
| `samples/audio/bn_plain.mp3` | full audio pipeline, including real Bangla ASR | byte-identical | [equivalence-bangla.log](equivalence-bangla.log) |
| `english sample.mp3`, first 20 seconds | full audio pipeline, including real English ASR | byte-identical | [equivalence-english.log](equivalence-english.log) |

An extended attempt on the entire 227-second English recording was stopped during its first CPU recognition pass after about twenty minutes, with available RAM down to about 2.5 GB while broad tests ran. It did not produce a comparison result; the regression gate uses the fixed 20-second excerpt.

## Contract checks

The focused module suite covers the registry and examples, all three spike modules through the executor, CLI and MCP stdio, versioned JSON/WAV/folder undo, stale dependants, prerequisites, cache, budgets, ordered locks, cancellation before commit, call events and redaction, tool schema export, and replay. The final focused log is [modules-focused.log](modules-focused.log) (30 passed, two slow equivalence cases deselected); the smaller CLI-only run also passed ([log](cli-replay.log)). A cold import of `vt.modules.registry` measured 57.8-84.6 ms across five fresh processes ([measurements](registry-import-ms.log)).

The settled full fast suite passed 801 cases, skipped the one script-evaluation case that requires `VT_EVAL_MODEL=1`, and deselected the 67 slow cases ([log](fast-final.log)). The full slow suite then passed all 67 collected slow cases ([log](slow-final.log)). The Studio's New-flow smoke suite passed on an isolated server with `VT_DATA` under `qa_phase1` ([browser log](studio-flow-scratch.log)). It used port 8788 because port 8777 was already occupied by an unverified data set; no browser suite touched port 8765 or that occupied server.

After verification, the idle real Studio was restarted so its Python process loaded the new runtime. `GET /api/health` returned `ok: true`, API version 4; it listed 40 existing projects and zero active jobs. No browser suite was pointed at this server.
