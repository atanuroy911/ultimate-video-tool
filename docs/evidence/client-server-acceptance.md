# Client and processing server acceptance — 2026-11-03

The desktop client and processing server are independent roles. A native loopback companion remains on the client for Claude and Codex whether processing runs beside it or remotely. It authenticates to the selected server's Director broker; assistant MCP calls use that server. The server owns projects, rendering, discovery, engine installs and model downloads.

## Implemented

- Desktop companion outside the page lifecycle; both client assistants register independently, reconnect, refresh login readiness, cancel work when the selected server changes and release disconnected runs. Only the owning paired client may finish its run.
- Server identity in setup and Engines; server-native absolute folder validation, separate program/model roots, selected GPU and snapshot of installation choices.
- Existing engines discovered first. Separate managed copies use their own ports rather than taking over an existing service. Picture model recipe fitted to the selected GPU.
- Four setup screens: server/engine choices, storage, connect or install, checks. Existing Comfy model preparation is available directly after connection. It reviews missing files, indexed model folders and workflow readiness before any download. Existing Ollama with no model offers a recommended model pull.
- Fixed bundle catalogue overwriting the selected bundles list, unsupported vtengine setup choices, confusing loopback address labels and stale negative elapsed display.
- Same-version desktop upgrades compare packaged source fingerprints before reusing the local processing runtime.

## Evidence

- Real Windows Codex login and read-only list_projects MCP call to the GPU server passed; both local Claude and Codex registered through the native companion: client-remote-connection.log. Claude readiness was real; its task runner is covered by the existing runner tests, not a new full video run.
- Remote UI on http://192.168.123.47:8790: setup identifies roy-CT500, lists both GPUs and recommends RTX 3060 for managed installs; existing Ollama and ComfyUI connect via server loopback. Missing-model inspection finds all fitted FLUX.2 Klein 4B files installed; Use recommended models completes workflow validation with no download. Four-step navigation and final Done were exercised. Screenshot: client-server-setup.jpg.
- Native companion, Director runner and bootstrap update Node regressions pass. Python contract checkpoints: architecture-contract.xml (46 passed), companion-final.xml (10 passed), setup-roundtrip.xml (14 passed). These overlap and are not an aggregate count.
- Final Python architecture acceptance: architecture-acceptance-final.xml (45 passed, 0 failed); documentation checker passes (client-server-docs.log).
- Per-user Windows installer upgrade exited 0. Installed app.asar contains the new companion, Codex runner and status worker. Prior connection preference was backed up; client now targets the authorized GPU server. Installed client startup log confirms the selected GPU server, and Windows enumerated its Ultimate Video Tool Studio window. Native visual inspection could not complete because app access approval timed out; the remote Studio UI was visually verified in the browser.
- Studio production typecheck/build passes: architecture-build.log.
- Windows installer built successfully: client-architecture-installer.log. Packaged app.asar includes ws, both assistant runners, the native companion and background status worker.
- Installer SHA-256: fdfcf3e7b19dec65b1b44e64a9d7352cabc1ab27bd2de93edc7842bd8e363eaa.

## Boundaries

- Existing ComfyUI downloads go to folders the engine already indexes. Choosing an arbitrary new folder requires a separate managed install; setup does not silently edit or restart an external engine. Existing Ollama's storage is owned by that running Ollama; managed copies support a chosen model root.
- Full clean Comfy/Ollama downloads and a clean Linux desktop install were not performed in this architecture check. Install plans/path/GPU routing are regression-tested. Existing GPU engine generation/export was tested in the earlier home-server installation record.
- No second ComfyUI, existing-engine service changes, training changes or changes outside /home/roy were made on the GPU machine. Only the isolated Video Tool user service was updated/restarted.
- The Windows installer is unsigned. No GitHub release or push was performed.
