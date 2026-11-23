# Independent client and processing server

The owner explicitly rejected bundling the video workspace with the processing server and requested two independent project directories. This supersedes the earlier combined-desktop/server-edition packaging.

## Ownership

- `client/`: Studio editor source and built assets, native desktop client, local assistant companion, authenticated loopback transport to the chosen processing server, client dependencies/build/tests. No Python, engine installer, renderer or server program is shipped with the client.
- `server/`: Python processing/API implementation, engine/model management, render runtime/assets, native server control panel, server dependencies/build/installers/tests. No Studio editor source or build is shipped or served by the server.
- Repository coordination remains at the root: documentation, shared integration tests, developer install/update entry points and CI. No symlinks disguising the old runtime layout.

The client serves its own UI and forwards API/media/WebSocket requests to its selected server. Pairing remains server-controlled, and local Claude/Codex registration targets the selected server. A local server is a separately installed application; choosing local processing must no longer bootstrap a server hidden inside the client.

The server browser landing page is management only. Editor API contracts and existing processing/project data are preserved. The owner's desired project-storage location has not been confirmed, so moving source and removing the bundled workspace must not silently move or delete user projects or change storage ownership.

## Migration and acceptance

1. Move product-owned source and resources into the two roots; preserve all existing uncommitted changes, data and installations.
2. Split desktop entry points, manifests, dependency locks and artifact allowlists.
3. Add a local client UI transport with protected loopback access and selected-server proxying; remove server fallback serving the editor.
4. Update launchers, packaging, CI, developer PS1/Bash installation/update scripts and current documentation to the new roots.
5. Build both products, inspect their package contents for cross-bundling, run transport/port/assistant/backend regressions and inspect the client UI plus server-only landing/control UI. Keep artifact/installation results distinct from full generation acceptance.
