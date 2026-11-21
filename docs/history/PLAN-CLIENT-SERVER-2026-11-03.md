# Client companion and processing server

Owner clarification: the desktop client always has a small native companion for Claude/Codex. Processing may be installed beside it or on another computer. The paired processing server owns projects, engine discovery, installations, models and rendering. Engine/model locations are paths on that server, never paths on the client PC. Existing engines are discovered before offering another installation.

Implementation sequence:
1. Make target identity and storage explicit in setup and plans; snapshot choices before an install job starts. Choose program and model roots on the processing server.
2. Keep an authenticated loopback-only native companion in the desktop client in both modes. Move the assistant-to-server connection out of the page lifecycle, reuse the server broker and add Codex alongside Claude. Assistant MCP calls always target the selected processing server.
3. Offer reuse of discovered engines and download only missing model files. Allow a chosen model location only when the existing engine already reads it; otherwise give an actionable plan instead of downloading unusable files or changing another installation silently.
4. Simplify setup into server identity, inspect/reuse or install, locations/plan, and progress. Preserve lower-level engine controls.
5. Test both local and remote targets, path validation, missing/already-installed models, assistant routing, reconnects and installer plans. Verify the remote server UI without installing another ComfyUI or altering the owner's existing services.

Important initial gaps: desktop remote mode currently kills its local Python processing server and relies on page WebSocket registration for Claude; Codex has MCP registration but no automatic Director runner. Setup says “this computer” ambiguously; engine root is fixed while only model location is configurable. Existing-Comfy preparation chooses folders automatically and has no user location selection. The default Comfy installer uses port 8188, risking a collision with an existing instance.

Outcome: implemented and deployed to the isolated GPU server; see [acceptance evidence](../evidence/client-server-acceptance.md). Native companion, real Codex MCP routing, setup walkthrough, existing-engine reuse, fitted-model workflow and Windows installer packaging were verified. Clean full engine downloads and Linux installer acceptance remain explicitly unmeasured.
