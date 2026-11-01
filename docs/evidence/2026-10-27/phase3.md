# Phase 3 evidence: surfaces and the live director log (2026-10-27)

| What | Where | Proof |
|---|---|---|
| REST: list, describe (with the provider tool shape), dry-run, foreground and background call | `vt/server/modules_routes.py` | `tests/test_modules_api.py` (4 tests) |
| Log endpoints: calls (after, level, group, search), one call, technical tail, zip download, cancel | `vt/server/log_routes.py`, `vt/modules/calls.py::read_calls` | `tests/test_modules_api.py::test_log_filters_one_call_download_and_cancel` |
| Events over the existing WebSocket: `call_started`, `call`, `ticket` (start and finish, with the estimate) | `vt/server/modules_routes.py::_start`, `vt/modules/executor.py` | `tests/test_modules_api.py::test_background_call_streams_events_and_can_cancel` |
| Technical capture: warnings and errors any library logs during a call, bounded to 2,000 lines, secrets removed | `vt/modules/calls.py::capture_technical`, `vt/modules/executor.py` | `tests/test_modules_calls.py::test_logged_warnings_during_a_call_reach_the_technical_log` |
| MCP: `module_catalog`, `module_describe`, `module_call` over stdio, the 31 older tool names untouched | `vt/mcp/server.py` | `tests/test_mcp_stdio.py` |
| The Details sheet: button on Making, Result ("How this was made") and the editor, key `L`, filters, search, expandable rows, running rows with cancel, Technical output switch, Copy, Download | `studio/src/log/DirectorLog.tsx`, `LogRow.tsx`, `TechnicalOutput.tsx`, `useCallLog.ts`, `studio/src/store.ts::onCallEvent` | `studio/e2e/log.mjs`: 13 passed, log in `docs/evidence/2026-10-27/e2e-log.log`; looked at: `docs/evidence/2026-10-27/shots/log-sheet.png` |
| Whole fast suite after the change | | no failures (all tests ran to 100 %) |

**Not built in this phase (honest list)**
* The MCP tool list is not generated one tool per module (140 tools would flood an assistant's context). The three generic tools reach every module; the 31 original names were left exactly as they were, so the planned "alias" test has nothing to compare and was not written.
* A module call logged only when it finishes: a running call shows as a live row from the events, and appears in the list once it has finished.
* The expanded row has *Why*, *Used*, the fix and the raw call; the *Re-run this*, *Undo this* and *Open the file* buttons and the result thumbnails are not built.
* The sheet is a right-hand sheet at every width; the bottom-sheet form for phones is not built.
* Ticket progress is the start and the finish of a call plus elapsed time against the estimate; modules do not yet report a fraction of their own.
