# Open issues (found while building, to fix later)

Newest first. Each line: what is wrong, where it was seen, how bad.

## 2026-11-22 (C7)
- **First picture is slow with the card cold:** `make_picture` took 42 s the first time (model load), 12 to 14 s after. Fine, but the agent should be told to wait. (C7)
- **Kokoro warns "words count mismatch on 100% of the lines"** for a one-sentence test; word timing may be rough for agent speech. (C7, minor)
- **Media bin holds pictures and clips only**, so `speak` saves a WAV under `agent_audio/` that no scene can use yet. Needs a place in the bin or a voice-over slot. (C7)
- **Codex** is not available (owner: ignore for now; ChatGPT app is installed, not the Codex command line).

## Carried over
- gemma4:e2b cannot write valid shots (they get dropped with a note); Claude can.
- Video quality: text clipped ("outdoo|"), a tiny icon, empty stretches, stick figures overlapping (PLAN-PERFECT).
- cuDNN crash that stops the server now and then (F1); the server manager does not restart a crashed server.
- The Claude Code tab has a model chooser (fake-agent test only; the real adapter has not been tried with each model); it has not been tried on a rebuilt installer (W12.6).
- Studio reloads after the agent turn ends, not live while it edits (W14).
- Clips (FramePack, Wan 2.2 5B) and the voices Chatterbox, Qwen3-TTS, OmniVoice and Bangla are not measured yet (C7).

## 2026-11-22 (C8)
- **"Open in VS Code" opens the agent folder only.** Claude Code inside VS Code has no Video Tool tools there, because giving it the server key means writing the key to a file. Needs the small VS Code extension (C8 rest) so the key stays in the app.
- **Chatterbox Turbo is far too slow here:** about 17 s of work for each second of speech (56 s for 3.2 s) on this laptop, on the card or the processor alike. A 1-minute video would take ~17 minutes. Look at whether the ONNX run really uses the card (probably the CPU build of onnxruntime), or use it only for short lines. (C7)
- **Qwen3-TTS, OmniVoice, Bangla voices** are not installed or measured; each needs a model download and an engine recipe that does not exist yet. (C7)
- **Server restart after a crash (F1) is written but not tried live:** `server/desktop/main.js` now starts the server again after an unexpected nonzero exit (3 times in 10 minutes at most). It is only syntax-checked; it needs a test that kills the server on purpose on a rebuilt Server app.
- **W14 is half done:** the change event names scenes and who (only when the MCP server acted in the last 4 s), the Studio toasts it. Still missing: the event from every save, `by` for person and director, the flash on changed clips, queued refresh during a drag, undo covering the agent.
- **Real Claude Code asking for a picture and speech (C7 check) not run yet:** `client/studio/e2e/desktop-agent-media.mjs` is written, but `/mcp` only exists when the scratch server listens beyond loopback (`--host 0.0.0.0`), and this session's safety check refused to start it that way. Needs the owner's OK (or a loopback-only test switch on the server), then run: `VT_SERVER=http://127.0.0.1:8791 VT_PROJECT=c6-shot node e2e/desktop-agent-media.mjs`.
- **VS Code extension (`client/vscode/`) is written but never run inside VS Code** (only its helper functions are tested, `node client/vscode/test.js`). It is not packaged or published; to try it: open VS Code with `--extensionDevelopmentPath=client/vscode`. It cannot write shots, only preview them; live "edits in VS Code show in the app" (C8 check) is not built.
