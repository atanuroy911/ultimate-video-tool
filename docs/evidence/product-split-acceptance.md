# Independent products — 2026-11-03

The owner required separate client/server directories and explicitly rejected bundling an editor workspace with the server. This record supersedes the earlier combined server-edition acceptance notes.

## Source and distribution boundary

- client/studio owns the editor, creation, timeline, shorts, sharing and settings interface.
- client/desktop owns the native client, local UI transport and Claude/Codex companion. Its only production npm dependency is ws. Its packaged resources contain app.asar and studio; there is no app-src, Python bootstrap, renderer or engine/model environment.
- server/vt owns processing and API contracts. server/renderer, server/assets and server/design are processing resources. server/desktop is the management-only native application; server/packaging holds headless install resources. Python metadata/lock are in server/.
- The server's / and /manage routes are standalone management pages. It never falls back to the editor for /new, /settings or project routes. No Studio source/build is in the server product or full processing archive.
- The client serves its own UI and forwards API, media range requests and WebSockets to the selected server. A native session secret protects its loopback listener, and separate Electron partitions isolate pairing for each processing server. The local secret is stripped before forwarding.
- Existing project/data locations were preserved. No user-data ownership migration was inferred from the source split. Old combined installers/source snapshots are preserved under dist/legacy-combined rather than used by either product.

## Verification

- product-split-final.xml: 54 passing focused Python tests, including existing editing APIs and the new product/package boundary contracts.
- product-split-boundaries.xml: 12 passing package/source boundary checks after final source guard updates (overlaps the broader selection).
- Node: real HTTP/WebSocket client transport, authenticated companion, Director runner, server control, occupied-port handling and same-version bootstrap refresh checks pass.
- Contained server manager: Engine settings and logs open within the same native window, with Back navigation. Electron action/UI-state tests verify internal views, no external browser call and denial of native-control IPC from the embedded engine page. Linux uses the installed GTK/WebKit view; its manager and WebKit process were checked on the GPU server. Native click-through visual acceptance remains a separate limit below.
- The Windows containment update installed with exit code 0; the installed app.asar contains both internal views and its processing API resumed with the retained environment/data. Artifact hashes are recorded in product-split-artifacts.json.
- Final installed settings route returned HTTP 200 with its loopback/file embedding policy. The native server window was enumerated after launch; accessibility and monitor capture were unavailable, so native visual acceptance is not claimed. The additional three product-boundary tests passed in contained-product-boundary.xml; their process lingered after reporting and was stopped.
- product-split-storage.xml: 9 passing storage/path and live-caption recovery checks after preserving legacy checkout data locations.
- Developer installer: real isolated client-only install and update pass on Windows and Linux, with spaces in paths, existing data preserved, no server Python environment and the install lock released. PowerShell parse/readiness and Bash syntax pass. A full clean server dependency installation through these scripts has not been repeated in this check.
- Client production typecheck/build and independent Windows client/server installer builds pass. Windows per-user upgrades of both editions exited 0 and retained data/environments. The installed client startup log confirms local UI with the selected GPU processing server; installed Windows server is running its processing API on 127.0.0.1:8790.
- Actual package contents were inspected: client resources are app.asar/app.asar.unpacked/studio; server resources are app.asar/app.asar.unpacked/app-src, with no Studio. Client installer is approximately 82 MB; processing server installer approximately 237 MB. Both are unsigned.
- The authorized GPU server now serves management only at http://192.168.123.47:8790. Its old app/studio folder was moved to a separate backup under /home/roy. Existing ComfyUI/Ollama and training were not changed. Its native Applications/tray manager uses Engine settings, not a video workspace.
- Browser inspection confirmed the remote management landing page and the independently served client at local :5173, paired against the GPU API; projects and the three-step New video flow load. Screenshots: product-split-server.jpg and product-split-client.jpg.
- Documentation structural/facts checks pass. CI and release jobs use the independent roots and avoid generating server processing assets in client builds.

## Developer installation

scripts/dev-install.ps1 and scripts/dev-install.sh share scripts/dev-install.mjs. Roles: client/server/both. Actions: install/update/launch/check. Private tool/data roots, vendor-checksummed Node fallback, uv/Python for server only, role-specific dependency setup, client build, launchers, fast-forward-only source updates, dirty-checkout preservation, four-hour update checks and JSON readiness are implemented. See docs/DEVELOPMENT-INSTALL.md.

## Limits

This is focused architecture/packaging acceptance, not a full all-feature regression, new GPU-generation evaluation, Linux native package install or GitHub release. Native window/tray/uninstaller controls were not all clicked through; browser UI and process/API/package checks are distinguished above. Full-removal uninstall was intentionally not exercised against user data. Windows uninstall defaults to keeping environment/data; manual full removal clearly warns and targets only that edition's private folder, preserving external custom folders and independent engines.
