# Fresh Ultimate Video Tool server in roy's home

Installed at the owner's request on 2026-11-03. The owner selected a fresh Video Tool server using the existing ComfyUI, rather than a second ComfyUI installation.

- UI: `http://192.168.123.47:8790` (pairing required on new devices).
- Application, private Python 3.11/CPU dependencies, private Node 22, renderer and assets: `/home/roy/ultimate-video-tool-server`.
- Fresh settings/projects: `/home/roy/ultimate-video-tool-server/data`. No old projects, accounts or settings were imported.
- Real generation fixtures remain separately in `/home/roy/ultimate-video-tool-server/qa`.
- Launcher: `/home/roy/ultimate-video-tool-server/run-server.sh`.
- User service: `/home/roy/.config/systemd/user/ultimate-video-tool.service`. Enabled and active; starts at roy's login. Linger is disabled, so no promise of startup before login. Enabling linger would require a system-level change outside the authorized home-only scope.
- Existing ComfyUI on 8188 and Ollama on 11434 are reused. Their installations and services were not edited, restarted, or replaced. ComfyUI reports the RTX 3060; the V100 remains occupied by the owner's separate work.
- No SSH password was stored in source, deployment configuration or these notes. Future maintenance helpers read `GPU_PASS` from the invoking environment.

## Checks performed

The remote UI was opened from this PC, paired, and visually checked with zero projects. New Video shows Best available director, Best available voice (Breeze TTS / OmniVoice on ComfyUI), and Let the director choose for this script as selected defaults.

Existing ComfyUI answered with 1,061 nodes. A real Breeze design request produced 2.24 seconds of speech; cold start took 123.8 seconds. FLUX.2 Klein generated the test image in 86 seconds. The new installation composed and rendered a frame, which was downloaded and inspected. Its real test export contains 1080×1920 H.264 video and AAC audio, duration 2.24 seconds. This is an installation/engine smoke test, not an evaluation of full Director storytelling quality or precise speech alignment.

Evidence: [generation report](../evidence/server-install/result.json), [frame](../evidence/server-install/frame.png), [export probe](../evidence/server-install/export-check.txt). The test MP4 is available locally in docs/evidence/server-install/installation-check.mp4 (large media is ignored by git).

Best available voice resolves to an actual ready, language-compatible engine at project creation and records that choice. Ready expressive ComfyUI workflows are preferred; the existing Breeze/OmniVoice policy chooses by language and direction. Explicit user choices remain authoritative. Director voice modules use the same defaults. Image generation consults installed model/node information before choosing its default recipe. These are capability/quality preferences, not a universal claim that one model is best for every script.

The full-server archive option (`scripts/make_engine_package.py --studio`) includes the UI, visual assets and renderer; the existing headless archive remains available. Private CPU dependencies avoid installing another CUDA environment into the owner's existing engine stack.

Validation: 28 backend/voice/scene/packaging cases passed, 19 Director-module cases passed, final voice/Direction regression passed, and Studio production build passed. Linux generation/rendering was exercised on this real installation.
