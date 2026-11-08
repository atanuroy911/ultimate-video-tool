# Setup banner and old director devices — Done by codex

2026-11-07. This covers items 3 and 4 in section 2 of `docs/plans/CODEX-NEXT-STEPS.md`.

The setup banner now distinguishes an explicit engine choice from an automatic discovery result on a new installation. The launcher’s explicit `existing`, `own` and `off` modes continue to count. An explicit engine address also counts. Default discovery can save usable endpoints or an automatic `off` result while setup remains open. An earlier explicit setup decision survives later automatic placement. Existing stored engine records and legacy addresses retain their prior interpretation because they carry no provenance. The Studio already keeps “Later” in local storage and gates the banner on the API’s `done` value.

The director list now applies its existing 60-day history limit on every read. It shows every live connection. When saved offline registrations have the same assistant and named computer, the newest one is shown unless a live registration already has that name. This is display grouping only. The history is retained within its original age limit, and choosing an old ID still follows that ID’s normal fallback path. Generic `This PC` names are kept separately because they do not identify a named computer.

The three new director-list tests failed on the previous code. The simulated explicit launcher reached `/api/setup` with `done: true` before and after the provenance fix. The default automatic launcher reproduced `done: true` before the fix even when no engine was available. Final tests use temporary settings and fake hardware/engine probes. They cover reachable and unavailable automatic choices, explicit `off`, and a second automatic launch after the owner made a choice.

From `server`, the final selection passed 22 tests with six existing FastAPI lifecycle deprecation warnings.

```powershell
..\.venv\Scripts\python.exe -X utf8 -m pytest -q -c NUL --rootdir=.. ..\tests\test_engine_placement.py ..\tests\test_director_choice.py ..\tests\test_one_director.py::test_a_computer_that_was_connected_is_remembered_as_not_connected_across_a_restart ..\tests\test_setup.py::test_a_server_whose_engines_were_all_chosen_is_not_asked_to_set_up_again
```

The read-only installed-server check on port 8790 returned `done: false` and `step: welcome`. Its saved setup choices and resolved engine modes were remote Ollama, remote ComfyUI and off VoiceStudio. The director list returned two live helper/assistant registrations and one offline registration. The live banner check stays open because the running server still reports `done: false`. The request used no credentials, and server state and installation were left alone.

The server manager obtains Electron’s single-instance lock before it creates the manager, and the second-instance event shows the first window. The manager creates one tray object. Both JavaScript files pass `node --check`. The installed Windows tray count and the reported duplicate icon still need an observed check in the installed app.
