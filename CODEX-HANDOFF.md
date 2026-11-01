# Handoff for Codex (and any other agent)

The owner works with Claude Code and Codex interchangeably. Read this file first, then `WORKLOG.md` (newest entry at the top) for what was
done and what is in progress. Update both when you stop: what you did, what you verified, what is left.

## The product in one paragraph

Video Tool turns a voice recording, a typed script or a link into a faceless short explainer video (Bangla, Banglish and English first).
Python package `vt/` (FastAPI server, pipeline, director, renderer driver), `renderer/` (HyperFrames HTML compositions rendered by Chrome),
`studio/` (React web UI, served by the server), `desktop/` (Electron shell). Engines: Ollama (planning AI), ComfyUI (pictures/clips),
VoiceStudio (voices). **Retention is the metric**: every change should make people watch longer.

## The owner's standing rules (do not break)

1. **UI wraps everything.** Users never run commands after install. Every capability is one function in `vt/`, exposed three ways: an
   `/api` route the Studio uses, a `vt` CLI command, and (where useful) an MCP tool or module. Never ship a CLI-only feature.
2. **Never install into global Python.** Use `.venv` and `.tools/uv.exe` (Windows) / `.tools/uv` (Linux). Never `pip install` system-wide.
3. **Windows and Linux** now, macOS later.
4. **Never invent facts** (numbers, quotes, screenshots). AI first, rules as the safety net.
5. **Commit and push after every tested step**, on the current branch (`client-server`). Never force-push, never push to `main` without asking.
6. Connecting Claude/Codex must be one click in the app, also when Claude runs on a different computer from the server.
7. Follow Apple design principles (clarity, deference, depth); the design-auditor skill is at `C:\Users\Roy\design-auditor\SKILL.md`.
8. "Licensing is not a concern. Don't ask; finish the job." Decide, don't ask, unless it is the owner's own system/config.

## Environment (this PC, Windows)

- Repo: `C:\Users\Roy\Desktop\ultimate-video-tool`, branch `client-server`, remote `origin` (GitHub atanuroy911/ultimate-video-tool).
- Python: `.venv\Scripts\python.exe` (3.11). Sync: `.tools\uv.exe sync --extra dev --extra cu124` (a GPU extra is required; `python -m vt.gpu_detect` names the right one). Tests: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W ignore tests/`
  with ffmpeg and node on PATH:
  `C:\Users\Roy\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin` and `C:\Program Files\nodejs`.
  `tests/test_sfx.py::test_mixer_levels_and_determinism` was a known failure (assets were lost; now regenerated, re-check).
  Render tests fail with "spawn UNKNOWN" only when the machine is overloaded (the owner runs ML training on it); rerun when idle.
- Studio typecheck: `cd studio && npx tsc --noEmit`; build: `npm run build`.
- GPU server: `roy@192.168.123.47` (Ubuntu, V100 16 GB + RTX 3060 12 GB, CUDA driver 580). It hard-resets sometimes (hardware); keep one SSH
  connection per task. Our install: `/mnt/bigdata/video-tool-server/{app,data,python,cache}`; never touch `/mnt/bigdata/video-tool`
  (the owner's older work) or the system services (comfyui 8188/8189, ollama 11434, voicestudio 3900). `vt server` runs there on port
  8767 (8765/8766 taken), started by hand: `cd app; VT_DATA=../data .venv/bin/python -m vt.cli server --name "GPU server" --comfy existing
  --ollama existing --voicestudio existing --port 8767`. Autostart is the owner's decision (Engines page, This server, Start by itself).
- This PC's engines point at the GPU server (Ollama `http://192.168.123.47:11434`, ComfyUI 8188 + worker 8189), saved in settings.

## Where things are (recent work)

| Area | Files |
|---|---|
| Client/server (CS1-CS6 done) | `docs/plans/PLAN-CLIENT-SERVER.MD`, `vt/server/serve.py` (guard, pairing, /mcp), `vt/server/clients.py` (device tokens), `vt/server/discovery.py`, `vt/server/uploads.py`, `vt/engines/placement.py`, `desktop/` (connect screen, discovery, assistants, MCP bridge) |
| One-click assistants | `vt/assistants.py` (+ `/api/assistants`, `vt assistants`), `desktop/assistants.js`, `desktop/mcp-bridge.js`, `studio/src/pages/AIAssistants.tsx` |
| Retention measurement | `vt/retention.py` (scorecard incl. picture hold + fill), `vt/judges.py` |
| Craft rules (from reference skills) | `vt/craft.py` (RULES, `check`, `fix_hook`), modules `craft.rules` / `craft.check` in `vt/modules/defs/craft.py` |
| Video lab | `scripts/video_lab.py`; outputs in `C:\Users\Roy\Videos\Video Tool Lab\round-NN\` (mp4, sheets, report.md); lab server: `VT_PROJECTS="C:\Users\Roy\Videos\Video Tool Lab\projects" vt studio --port 8771 --no-open` |
| Reference skills (read-only clones) | Claude's scratchpad `refs/` (i-hate-editing, awesome-claude-video-skills and 7 skills from it); not in the repo |

## Open work, in priority order

See the top entry of `WORKLOG.md` for the live list. At the time of writing:
1. lemo-opuscar film styles (github.com/lemomo-ai/lemo-opuscar): read, map to our themes/looks, build as selectable styles.
2. Craft module exposed everywhere: MCP tools `craft_rules` / `craft_check`, rules inside `get_planning_task` / `get_script_task`,
   `vt craft` CLI, `/api/projects/{id}/craft`, Review page checklist.
3. Remote Claude (Claude on the owner's PC, server on the GPU box): a way to send local media to the server (upload URL + token).
4. All NVIDIA GPUs / CUDA versions natively: detect compute capability + driver, choose torch / onnxruntime-gpu builds per CUDA flavour, CPU fallback.
5. Video lab round 2 with the new code; compare with round 1 (`video_lab.py --compare`); then every combination (kinds x use cases x shapes x
   languages x styles), saved on this PC for the owner to judge; look at contact sheets and fix.
6. Profile the Studio timeline smoothness before any Rust/Tauri decision.
7. Speed: the AI context step fails on gemma4 (section ids) and costs ~150 s; the post-plan QA takes ~6 min.
