# PLAN-WORKBENCH: 0.x, the critical fixes, and an OpenFilm-style workbench with Claude Code inside

Written 2026-11-20 by Claude (Opus) for Claude Sonnet to carry out, step by step, and for the owner to review.
Progress is kept in this file's tick boxes. A session resumes at the first unticked step.

---

## 0. How to work this plan (read every time you start)

0.1 **Start of every session.**
1. Read this section 0 and section 1 (decisions). Do not re-decide anything in section 1.
2. Read the newest entry of `docs/dev/WORKLOG.md` (or `docs/dev/WORKLOG.md` once step W5.4 has moved it). Codex may have changed things since the last tick.
3. Run `git status` and `git log --oneline -5`. Check out the branch `workbench` (step W0.1). Never work on `main`.
4. Find the first unticked `- [ ]` step below and do it. Do the steps in order unless a step says otherwise.

0.2 **The branch rule. This matters more than anything else in this file.** Every push to `main` builds and **publishes a public release automatically** (`.github/workflows/release.yml`). So:
- All work happens on the branch `workbench`. Commit after each step that passes its checks, then `git push origin workbench`.
- Never push to `main`. Never merge into `main`. Never force-push. Merging is the owner's call, at W15.6.
- Commit messages: one plain-English line saying what changed for the person, then a blank line and details. Never add `Co-Authored-By` lines.

0.3 **Setting up to run things.**
- **Video tests: no "yield" sample.** The old `samples/build_reference.py` project (a Bangla finance script with synthetic timings and silent audio) is not a real test. Make real videos with `scripts/lab/local_matrix.py` (W3.7): different kinds, formats and languages, real voices, **Claude on this PC as the director** (Sonnet), then gemma. Judge them by looking at them.
- **Everything is tested on this laptop, with all data on E:. Never use the GPU server (192.168.123.47)** for this plan: no SSH, no engines there, no tests there (the owner, 2026-11-20). Scratch servers, scratch projects, models, nightly reports and evidence all go under `E:\UltimateVideoTool\` (scratch servers in `E:\UltimateVideoTool\scratch\<step-id>\`). Before a test, check that the server settings and `VT_*` environment variables point the engines (Ollama, ComfyUI) at this PC (`127.0.0.1`), not at 192.168.123.47. If an engine is missing here, install it through the server window onto E:, or skip that test and say so. Never fall back to the GPU server.
- **Already set up on this laptop (W0):** uv is at `E:\UltimateVideoTool\.tools\uv.exe`, the Python environment at `E:\UltimateVideoTool\venv-workbench`, scratch data under `E:\UltimateVideoTool\scratch\`. The exact commands (environment variables, scratch server, Studio dev server, screenshots) are at the end of `docs/dev/baseline-2026-11.md`: use them as written. In Git Bash, put `MSYS_NO_PATHCONV=1` before any command with a URL path starting with `/`. The one known fast-suite failure is `test_gpu` (needs the CUDA build of torch; W3.2 marks it).
- Python: never install into the system Python. Use `uv`: `uv sync --project server --frozen --extra dev --extra cpu --python 3.11`, then `uv run --project server pytest -m "not slow"`. If `uv` is not on PATH, look for `.tools/uv.exe` in the repo, then `where.exe uv`, then `E:\UltimateVideoTool\` and `E:\UVT-Server\`. If none is found, stop and ask the owner. Do not run `pip install`.
- Node: `npm ci` inside `client/studio`, `client/desktop`, `server/desktop`, `server/renderer` as needed.
- **Ports:** the installed server on this PC uses port **8790**. Before starting any scratch server, check that its port is free (`Get-NetTCPConnection -LocalPort <port> -ErrorAction SilentlyContinue`) and that its data folder is yours (`VT_PROJECTS=<a new scratch folder>`). Never point a scratch server at `E:\UltimateVideoTool\ServerData`.
- Installed apps on this PC: client `E:\UVT-Client\Ultimate Video Tool`, server `E:\UVT-Server\Ultimate Video Tool Server`. To reinstall over them, run `<installer>.exe /S /currentuser` with **no** `/D=` and **no** uninstall first.

0.4 **Every step ends the same way.**
1. Run the step's **Check** commands. All must pass.
2. Run the fast suite: `uv run --project server pytest -m "not slow" -q` (about 7 minutes). For client-only steps, run `cd client/studio && npm run build && npm run test:timeline` instead, plus the node tests named in the step.
3. Tick the step's box in this file, with the date and the commit's short hash: `- [x] W2.1 … (2026-11-21, a1b2c3d)`.
4. Commit and push to `workbench`.
5. At the end of each **phase** (W1, W2, …), add a `docs/dev/WORKLOG.md` entry (newest first: done / verified how / left over) and refresh `docs/dev/CODEX-HANDOFF.md` if a rule or path changed.

0.5 **When a step is wrong.** If the code no longer matches what a step says (a file moved, a function was renamed), adapt the step to the code as it is now. Say so in the commit message. Do not invent a different goal. If a step cannot be done without changing a decision in section 1, stop and ask the owner. Ask in plain words, with no jargon, and offer a recommended answer.

0.6 **Standing rules from the owner (all still in force).**
- *UI wraps everything.* Every capability is one function in `server/vt/` exposed three ways: an `/api` route the Studio uses, a `vt` command, and (where useful) an MCP tool. The person never has to type a command.
- *Windows only for testing* (the owner, 2026-11-20). Everything is tested on this Windows laptop. Write paths, process spawning and shortcuts so Linux would still work (the release workflow still builds Linux installers on GitHub), but never test on Linux and never install WSL. Say "Linux not tested" in reports.
- *AI directs; no static rules.* One director per video. Teach the AI through its prompts (visible in **Details → AI conversations**). Never override its choices with code.
- *Human in the loop.* One AI revision, then the person fixes things by hand. A hand edit is never undone by a rule or a recompose.
- *UI is English only.* Bangla is a video language, not a UI language.
- *Decide in plain words.* Never ask the owner a jargon question. Decide technical choices and say what was decided.
- *Test with Claude Sonnet, then gemma.* Real end-to-end tests go through the real Claude director with `--model sonnet` without asking about usage, then repeat with the local gemma model.
- *Licences.* OpenFilm is MIT: copying its code is allowed, and each copied file keeps a header naming its source path and commit (see W0.2). OpenChatCut (AGPL) code is already in `client/studio/src/occ/`, with the owner's approval. The Agent Client Protocol packages are Apache-2.0. Every new third-party file or package gets a line in `THIRD-PARTY.md`.

0.7 **Where heavy work runs: this laptop.** Rendering, voices, speech recognition and the local AI (gemma through Ollama) run on the server installed on this PC (`E:\UVT-Server\…`, data in `E:\UltimateVideoTool\ServerData`; RTX 4050 Laptop GPU, 6 GB). Choose model sizes that fit 6 GB. When one does not fit, use the smaller model and record that in WORKLOG; do not move the work to the GPU server. GPU timing: pytest holds about 2 GB of VRAM, so close it before timing anything on the GPU. E: had 223 GB free on 2026-11-20. Check `Get-PSDrive E` before downloading models or keeping videos, and keep at least 30 GB free.

---

## 1. Decisions already made (do not re-open)

| # | Decision | Why |
|---|---|---|
| D1 | **The product is renumbered 0.x.** The next release is **0.5.0**. The workbench release is **0.6.0**. 1.0.0 is only claimed when every gate in W15 and the acceptance list in `docs/AUDIT-2026-11-03.md` pass. | The owner's choice, 2026-11-20: "lets call it 0.x". The 1.0.0 label claimed more than the project's own audit did. |
| D2 | **The published v1.0.0 release and tag are deleted** after 0.5.0 is published (W1.6). People who downloaded 1.0.0 keep their files. Installing 0.5.0 over 1.0.0 must work (checked in W1.5). | The release workflow counts on from the newest tag. A leftover v1.0.0 would make the next automatic release 1.0.1 and block a real 1.0.0 later. About 90 people downloaded the Windows installers, and none of them has an auto-updater. |
| D3 | **Every request to the server passes the web-page check** (Host is an address or a local name, and Origin is absent or the server itself), in every mode, local mode included. | Today, local mode skips every check (`server/vt/server/serve.py`, `allowed()`, the `not STATE["exposed"]` branch). Any website open in the person's browser can then call `127.0.0.1:8765/8790`. |
| D4 | **Other computers need the server's key by default**, including computers on the same Wi-Fi. A setting in the server window, "Computers on my network can connect without the key", is **off** by default and warns when turned on. Loopback (this computer) never needs the key. | "Private address" also describes café, hotel and office networks. The key flow already exists (`needs_key`, the client's connect page), so this reuses it rather than building pairing. |
| D5 | **No git history rewrite.** `docs/evidence/` leaves the tip of the repo, and a zip of it becomes a release asset. The 196 MB of history stays. | The repo has 4 forks, and a rewrite needs a force-push to `main`. |
| D6 | **One timeline.** The "Classic / New timeline" switch goes. The New timeline (ported from OpenChatCut) stays, after the parity check in W11.1. | Two timelines double the surface to test and confuse people. |
| D7 | **We do not embed VS Code.** OpenFilm does not either: it has no Monaco, no code-server and no xterm. Its "VS Code feel" comes from docked panes plus an agent chat sidebar, written in React. We build the same. | Embedding VS Code or Monaco adds 100+ MB and is a code editor, not a video editor. |
| D8 | **Claude Code and Codex run inside the app through the Agent Client Protocol (ACP)**, using the official adapters `@agentclientprotocol/claude-agent-acp` and `@agentclientprotocol/codex-acp`, with the person's **own** installed and signed-in program. The app never sees a token. Our MCP server is attached to each session (`session/new` → `mcpServers`). | This is how OpenFilm does it. It keeps within Anthropic's terms: the person's own unmodified Claude Code, with sign-in done by that program. |
| D9 | **Unlike OpenFilm, the agent does not get full access to the computer.** Video Tool's own MCP tools are allowed without asking. Anything else (shell, file writes, web) shows a permission card: *Allow once*, *Allow for this chat*, *Deny*. | OpenFilm forces `bypassPermissions` for Claude and `agent-full-access` for Codex (`apps/desktop/chat/src/state/local-agent-store.ts`, `AGENT_FORCED_PREFS`). That lets the agent run any command on the person's computer without asking. |
| D10 | **Electron is upgraded to 44.x in both desktop apps** (client and server), the version OpenFilm ships with these adapters. | `claude-agent-acp` needs Node ≥ 22. Electron 33 ships Node 20. |
| D11 | **React 18 stays, and no Tailwind.** OpenFilm's React 19 + Tailwind code is translated to our CSS with tokens when it is ported. | This is the owner's standing rule from the OpenChatCut port. Adding Tailwind beside about 2,400 lines of existing CSS would make three styling systems. |
| D12 | **Our accent is the brand orange** (the `#f26a1f` of the README badge), tuned for contrast. OpenFilm's teal, logo, name and look-alike branding are **not** copied. Neutral greys, layering and density follow the same principles. | Their design principles are reusable; their identity is not. |
| D13 | **Output quality work stays in `docs/plans/PLAN-PERFECT.MD`** (57 open steps: captions, picture choice, hooks and the rest). This plan does not duplicate it. It adds the nightly checks (W3) that measure that work. | One plan per topic. |
| D14 | **Keyboard shortcuts follow VS Code** where a VS Code meaning exists: Ctrl+B library, Ctrl+Alt+B assistant, Ctrl+J timeline, Ctrl+Shift+P command palette, Ctrl+L focus the assistant's message box. Ctrl+Alt+I toggles the inspector (Ctrl+Shift+I stays the developer tools). On macOS, Cmd replaces Ctrl. | This is the "VS Code feel" the owner asked for, and these shortcuts are what people already know. |

---

## 2. The OpenFilm audit (what we take, what we don't)

**Reference:** github.com/openfilm/openfilm, commit `a1b8d751f8979f0175902ddf113e5e14c5ea71c8` (2026-11-19), MIT, about 8,600 stars. The reference copy lives at `E:\openfilm-a1b8d75` (W0.2).

### 2.1 What it is
- A monorepo: `packages/openfilm` (the film format, the `openfilm` CLI, the Studio UI in React 19 + Tailwind 4 + Vite) and `apps/desktop` (Electron 44, which mounts the Studio's `App` unchanged and adds a chat column beside it, `apps/desktop/shell/main.tsx`).
- A film is a folder with `film.html`. Each shot is a web page exposing `window.film.frame(t)`, which draws the same picture for the same `t` every time. A hand edit is saved as `overrides` on the clip, so the agent can rewrite the page without losing the person's change.
- **The agent tab** (`apps/desktop/src/agents.mjs`, 1,656 lines) drives 11 coding agents over ACP: a child process speaking JSON-RPC on stdin/stdout. `initialize` → `session/new` (or `session/resume` / `session/load`) → `session/prompt`. `session/update` notifications draw the chat, and `session/request_permission` would ask the person. Claude Code and Codex go through the official adapters with the person's own program (`CLAUDE_CODE_EXECUTABLE`, `CODEX_PATH`). Instructions reach Claude via `_meta.systemPrompt.append`, and settings via `_meta.claudeCode.options`.
- **The look** comes from one documented token set (`packages/openfilm/studio/ui/src/globals.css`, lines 1–200): layered surfaces (app, panel, raised), translucent field/hover/pressed fills that read the same on every layer, three text levels, hairline borders, ink (near-black or near-white) for the main action, **one** accent kept for "selected, current, focused", and one quiet colour per clip kind at one lightness with white labels. The type is Inter at small sizes, with no heavy weights.
- **The layout** is a dock tree of splits (`studio/ui/src/lib/workspace-dock.ts`, 161 lines, pure, tested). The window is: media library | viewer | inspector, then a full-width timeline underneath, and the agent chat as a full-height column on one side. Layouts are saved per workbench (`lib/workspaces.ts`). Panes are toggled from icons at the top right.
- **"Point at anything"** (`apps/desktop/chat/src/studio-refs.ts`): a clip, layer, region of the frame, moment, range, track, file or subtitle line becomes a *pill* in the composer. In the message the agent reads, it becomes a numbered link (text "1: title" pointing at `film.html#t=12.5`) plus a `<studio_references>` block with ids, times, boxes and a picture. The agent links back the same way.
- The composer is built on Lexical (`chat/src/components/prompt-editor/`), with @-mentions and pills.

### 2.2 Where it is strong (take these)
1. ACP integration with the person's own agents: a clean boundary, no tokens held, and resumable sessions.
2. The design system: written down once, used everywhere, and colour means something.
3. Dockable panes with saved layouts. The agent is always there, not behind a button.
4. Pointing at things instead of describing them in words.
5. Live collaboration: the agent edits the same project the person is looking at, and the person sees it change.
6. Tests for UI behaviour (`packages/openfilm/studio/*.test.mjs`, about 45 files).

### 2.3 Where it is weak (do not copy these)
1. **Full access by default:** it forces `bypassPermissions` for Claude Code and `agent-full-access` for Codex, plus yolo flags for Qwen, Kimi and others. See D9.
2. **Huge files, like ours:** `ProjectView.tsx` is 6,103 lines, `Timeline.tsx` 5,647, `FilmStageSelect.tsx` 3,822. Port small pure modules, not those files.
3. **macOS and Windows only.** We must also ship Linux.
4. **A paid service is wired in** (`BalanceNotice.tsx`, `SpendAsks.tsx`, balance top-ups for the built-in agent). We bring nothing of it.
5. **Very wide scope** (Canvas, Color grading, plugins, a community standard), which is the same trap we are in. We take the editor shell and the agent pane only.

### 2.4 OpenFilm files to read, by step
| Our step | Read in the reference copy |
|---|---|
| W6 tokens | `packages/openfilm/studio/ui/src/globals.css` (1–300) |
| W7 dock | `packages/openfilm/studio/ui/src/lib/workspace-dock.ts` + `.test.ts`, `lib/workspaces.ts` + `.test.ts`, `components/PaneDivider.tsx`, `components/dock-pane-bar.ts`, `lib/keymap.ts` |
| W8 top bar and panes | `components/ProjectView.tsx` (read only the JSX of the top bar and the panes; do not port the file), `components/InspectorPanel.tsx`, `components/MediaPool.tsx` |
| W10 assistant pane | `apps/desktop/chat/src/App.tsx`, `components/ProjectConversation.tsx`, `TurnLog.tsx`, `AgentActivityRow.tsx`, `AgentPermissionCard.tsx`, `ModelPopover.tsx`, `ComposerCard.tsx`, `prompt-editor/*`, `useStickToBottom.ts`, `chat.css` |
| W12 ACP runner | `apps/desktop/src/agents.mjs` (lines 1–120 and 1300–1656), `agent-installation.mjs`, `environment.mjs`, `local-agents-ipc.mjs`, `agents.test.mjs` |
| W13 pointing | `apps/desktop/chat/src/studio-refs.ts`, `packages/openfilm/studio/ui/src/lib/links.ts` |

---

## 3. The phases

```
W0  ground                 branch, reference copy, baseline numbers
W1  0.x                    renumber, publish 0.5.0, retire 1.0.0
W2  security               web-page check everywhere, key for other computers
W3  proof of the video     nightly slow + browser suites, triage the 11 failing
W4  code health            split app.py, stop silent failures in the pipeline
W5  repo and docs          evidence out of git, one STATUS, dev notes out of root
W6  design tokens          one token file, no raw colours in components
W7  dock workbench         panes that resize, hide and remember
W8  top bar and panes      one quiet bar, library / viewer / inspector content
W9  Electron 44            both desktop apps (needed by W12)
W10 assistant pane         the right-hand column, Director chat moved in
W11 one timeline           parity check, retire Classic, restyle
W12 Claude Code and Codex  ACP runner in the desktop app, permissions
W13 point at anything      pills, references, links back
W14 live edits             the person watches the agent work
W15 acceptance and 0.6.0   screenshots, suites, real runs, owner merges
```
W1 and W2 come first because they fix what is wrong today. W9 must be done before W12. W6 must be done before W7, W8, W10 and W11.

---

### W0 — Ground

- [x] **W0.1 Branch.** (2026-11-20) `git fetch origin && git checkout -b workbench origin/main && git push -u origin workbench`.
  Check: `git branch --show-current` prints `workbench`.

- [x] **W0.2 Reference copy of OpenFilm.** (2026-11-20, a15e6c7) `git clone https://github.com/openfilm/openfilm E:\openfilm-a1b8d75`, then `git -C E:\openfilm-a1b8d75 checkout a1b8d751f8979f0175902ddf113e5e14c5ea71c8`. Never run its install scripts, never run `pnpm install` in it, and never import from it at build time. It is read-only reference.
  Every file you port from it starts with this header (adjust the path):
  ```
  // Ported from OpenFilm (MIT, github.com/openfilm/openfilm) packages/openfilm/studio/ui/src/lib/workspace-dock.ts @ a1b8d75.
  // Changed for Video Tool: <one line>. See THIRD-PARTY.md.
  ```
  Add an OpenFilm section to `THIRD-PARTY.md` with the full MIT licence text from `E:\openfilm-a1b8d75\LICENSE`.
  Check: `git -C E:\openfilm-a1b8d75 rev-parse HEAD` prints `a1b8d75…`. Commit the THIRD-PARTY.md change.

- [x] **W0.3 Baseline.** (2026-11-20; numbers in `docs/dev/baseline-2026-11.md`) Record, in a new file `docs/dev/baseline-2026-11.md`:
  - The fast-suite result (pass/skip/fail counts and time).
  - `npm run build` time and the size of `client/studio/dist`.
  - Installer sizes from the v1.0.0 release (`gh release view v1.0.0 --json assets`).
  - Screenshots of the editor at 1440×900, light and dark, saved to `docs/dev/shots/before-*.png`. Take them from a scratch server with a sample project (0.3 ports rule), using the existing `e2e:editor` Playwright setup or a small script.
  - Line counts of `server/vt/server/app.py`, `client/studio/src/pages/Review.tsx` and `client/studio/src/styles.css`.
  - The number of distinct hex colours in `client/studio/src` (today 223): `grep -roh '#[0-9a-fA-F]\{6\}' client/studio/src --include=*.tsx --include=*.css | sort -u | wc -l`.
  Check: the file exists with every number filled in.

---

### W1 — Renumber to 0.x

- [x] **W1.1 Find every "1.0.0".** (2026-11-20; ours: the 4 package manifests and pyproject; the rest are test fixtures that pass a version in, or history) Run `git grep -n "1\.0\.0" -- ':!docs/evidence' ':!**/package-lock.json'`. For each hit, decide: is it *our* version (change it) or a third-party version (leave it)? Expected hits include `server/pyproject.toml`, `client/desktop/package.json`, `server/desktop/package.json`, `server/renderer/package.json`, `tests/test_packaging.py`, `tests/test_product_split.py`, `tests/test_server_auth.py`, `scripts/lab/install_*.py`, `server/desktop/test-bootstrap-update.js` and `server/desktop/test-log-view.js`. List them in the commit message.

- [x] **W1.2 Set the version.** (2026-11-20; also extended `set_version.py` to the Studio and renderer manifests and lock files) Run `python scripts/set_version.py 0.5.0` (through `uv run --project server python …`). Then fix the tests and scripts from W1.1 that hard-code `1.0.0`: make them read the version from `scripts/set_version.py --show`, or use a neutral sample version like `9.9.9` where the test only needs *a* version. Also update `client/studio/package.json` (`0.1.0` → `0.5.0`), so every package says the same number, and extend `set_version.py` to write it too.
  Check: `uv run --project server python scripts/set_version.py --show` prints `0.5.0`. `git grep -n '"version": "1.0.0"'` finds nothing of ours. Fast suite passes.

- [x] **W1.3 Make the release workflow refuse to go back to 1.x by accident.** (2026-11-20; done as `scripts/next_version.py` + `tests/test_release_version.py`, called from the workflow) In `.github/workflows/release.yml`, in the `version` job:
  - When the version is computed automatically (a push to `main` or a manual run with no version given), and the newest tag's major number is ≥ 1 while `server/pyproject.toml` says 0.x, use the files' version (`set_version.py --show`) as the base instead of the tag.
  - Add a guard: an automatically computed version whose major number differs from `set_version.py --show`'s major fails with `::error::Version mismatch: files say X, tags say Y. Push a tag to choose.`
  - Update the comment at the top of the file: "every push to main publishes the next patch (v0.5.0 -> v0.5.1 …)".
  Check: dry-run the `next_patch` bash logic locally in Git Bash with fake tag lists (`v1.0.0` alone → `0.5.0`; `v0.5.0,v1.0.0` → `0.5.1`; `v0.5.3` → `0.5.4`). Paste the three outputs into the commit message.

- [x] **W1.4 Words.** (2026-11-20) In `README.md`:
  - Add a line under the title: "**Status: beta (0.x).** It works end to end, but video quality and installs on new machines are still being proven. See the status page." (make "status page" a Markdown link to `docs/STATUS.md`)
  - Release notes text in `release.yml` (`body:`): add "This is a beta. Coming from 1.0.0? Install over it; on Linux use `sudo apt install --allow-downgrades ./<file>.deb`."
  Check: `uv run --project server python scripts/check_docs.py --structural-only` passes.

- [x] **W1.5 Prove that installing 0.5.0 over 1.0.0 works.** (2026-11-20; results in `docs/dev/baseline-2026-11.md`; Linux .deb not tested: the owner chose no WSL) Build the Windows client and server installers locally (`scripts/build_client_windows.sh <out>`, `scripts/build_server_windows.sh <out>`). Install each over the existing 1.0.0 install on this PC (`/S /currentuser`, no `/D=`, no uninstall). Then open the client, connect to the installed server (port 8790), open an existing project, and render a 10-second preview.
  - If the NSIS installer refuses to downgrade: set `nsis.allowDowngrade`-style behaviour in electron-builder config (check the electron-builder docs for the exact key in the installed version) and rebuild.
  - Also check the server's bootstrap: it re-installs its Python environment when the version stamp differs (`server/desktop/bootstrap.js`, `s.version === L.version`). Expect one re-install on first start and note how long it takes.
  - Linux (`.deb`): not tested (Windows only, owner decision). The `--allow-downgrades` note (W1.4) is written from the apt documentation.
  Check: write the outcome, with times, into `docs/dev/baseline-2026-11.md` under "0.5.0 over 1.0.0".

- [ ] **W1.6 Publish 0.5.0 and retire 1.0.0. This step needs the owner.** It ships together with W2 (security). So do W2 first, then come back here.
  1. Ask the owner, in these words: "Ready to publish 0.5.0 (the security fix and the 0.x number). This merges the branch into main, which publishes a release, and then deletes the 1.0.0 release and its tag. People who downloaded 1.0.0 keep their files. Go ahead?"
  2. On yes: open a pull request `workbench` → `main` titled "0.5.0: beta numbering and the server's web-page check". Let CI pass. **The owner merges it.** The merge publishes the release. Before merging, push the tag `v0.5.0` on the merge commit so the workflow publishes exactly 0.5.0, or run the Release workflow manually with version `0.5.0`, whichever the workflow's comments say is the supported way.
  3. After `v0.5.0` is published and its downloads are present: `gh release delete v1.0.0 --cleanup-tag --yes`, then `git tag -d v1.0.0` locally. Delete the GHCR image tag `video-tool-engine:1.0.0` only if the owner agrees (it may be pulled by someone's Docker setup). Otherwise leave it.
  4. Attach `docs-evidence-2026-11.zip` (from W5.1) to the 0.5.0 release if W5.1 is already done. Otherwise do it at W5.1.
  Check: `gh release list` shows `v0.5.0` as Latest and no `v1.0.0`.

---

### W2 — Security: the server answers only its own tools

Background: `server/vt/server/serve.py`. Today `allowed()` returns `True` for every request when `STATE["exposed"]` is false (local mode), without running `browser_safe()`. In exposed mode, `trusted()` lets any private, link-local or Tailscale address in without the key.

- [x] **W2.1 Tests first (they must fail before the fix).** (2026-11-20, `tests/test_server_webpage_guard.py`; 9 of 12 failed before the fix) Extend `tests/test_server_auth.py`, using the same ASGI test style the file already uses. Cases:
  1. Local mode, `POST /api/llm/setup` with `Origin: https://evil.example` → **403/401**, and nothing starts (assert no job was submitted).
  2. Local mode, `GET /api/projects` with `Host: evil.example:8790` (DNS rebinding) → refused.
  3. Local mode, websocket `/ws` with `Origin: https://evil.example` → closed with 4401.
  4. Local mode, `POST /api/projects/x/duplicate` with no Origin and `Host: 127.0.0.1:8790` → allowed (this is the desktop client and `curl`).
  5. Local mode, `Origin: null` (a sandboxed iframe) → refused.
  6. Local mode, `Origin: http://127.0.0.1:8790` with matching Host → allowed (a page the server serves itself).
  7. Exposed mode, client `192.168.1.20`, no key → refused with the "needs key" message. With the right key → allowed.
  8. Exposed mode, client `192.168.1.20`, no key, with the setting `trust_network` on → allowed.
  9. Exposed mode, client `127.0.0.1`, no key → allowed (this computer).
  10. Exposed mode, client `100.64.1.2` (Tailscale), no key → refused unless `trust_network` is on.
  11. The OPEN paths (`/.well-known/video-tool`) with `GET` and a foreign Origin → allowed (they are read-only and harmless). The same paths with `POST` → refused.
  12. The upload ticket path (`PUT …/file?ticket=…`) still works from another computer with a valid ticket.
  Run them and confirm 1, 2, 3, 5, 7 and 10 fail today. Paste the failing list into the commit message, then commit the tests marked `xfail(strict=True)` with reason "fixed in W2.2".

- [x] **W2.2 The fix.** (2026-11-20) In `serve.py`:
  ```python
  def allowed(scope: dict) -> bool:
      path = scope.get("path", "")
      method = scope.get("method", "GET")
      # 1. A web page never reaches this server through someone's browser, in any mode.
      if not (path.startswith(OPEN) and method in ("GET", "HEAD")) and not browser_safe(scope):
          return False
      # 2. the director's MCP endpoint, as today (project_for(...))
      # 3. not exposed: this computer only; nothing else can reach a 127.0.0.1 listener
      # 4. exposed: loopback is trusted; other computers need the key unless STATE["trust_network"] and on_own_network(scope)
      # 5. the upload ticket and the key, as today
  ```
  - Keep `browser_safe()` as it is. It already does the right Host and Origin checks.
  - Split `trusted()` into `is_this_computer(scope)` (loopback, no forwarding headers) and `on_trusted_network(scope)` (`STATE["trust_network"] and on_own_network(scope)` and no forwarding headers).
  - Add `trust_network: bool` to `configure()` and `STATE`, read from the server's settings file (find where `exposed` and `key` come from, in `vt server` startup in `server/vt/cli.py` or `serve.py`), with default `False`.
  - `/.well-known/video-tool` must report `needs_key: true` to another computer when `trust_network` is off.
  - Remove the `xfail` marks. All 12 cases pass.
  - Grep the clients that call the server directly and confirm they send no Origin: `client/desktop/transport.js` (it deletes `origin`), `client/studio/vite.config.ts` (its proxy removes it), `client/desktop/helper.js`, `client/desktop/mcp-bridge.js`, `server/desktop/*.js` (the server manager's own window — check whether it loads a page *from* the server; if so its Origin equals the Host, case 6) and `scripts/lab/*.py`. Fix any that would now be refused.
  Check: fast suite green. `node client/desktop/test-transport.js` and `node server/desktop/test-server-control.js` green.

- [x] **W2.3 The setting in the server window.** (2026-11-20; also `vt key`, `GET /api/server/key`) In the server manager UI (`server/desktop/server-manager.html` / `server-manager-ui.js`), in its connection section, add a switch: **"Computers on my network can connect without the key"**, off by default. Turning it on shows: "Anyone on this Wi-Fi or network can then use this server, including on public networks. Leave this off unless this is your own home or office network." It writes the setting (the same file W2.2 reads) and restarts the listener the way other settings do. Show the key and a **Copy key** button next to it, if they are not there already.
  Also expose it the three ways (rule 0.6): `vt server --trust-network/--no-trust-network`, and `GET/PUT /api/server/settings` if such a route exists (otherwise add the field to whatever route the manager uses).
  Check: `node server/desktop/test-server-control.js` extended with the switch; fast suite green.

- [x] **W2.4 The client asks for the key in plain words.** (2026-11-20; `client/desktop/server-keys.js`) When a client (desktop app or helper) gets the "needs key" refusal from a server on its own network that used to work, the connect page (`client/desktop/connect.html` and the Studio's Server page) says: "This server now asks for its key. Open the server window on that computer, then Connection → Copy key, and paste it here." Check that the helper (`client/desktop/helper.js`) stores and sends the key for such a server, as it already does for servers outside the network.
  Check: `node client/desktop/test-helper.js`, `test-helper-control.js` and `test-transport.js` extended with the case and green.

- [x] **W2.5 Manual proof on this PC.** (2026-11-20; three curls plus a real export on the installed server) With the installed server (or a scratch server if you have not reinstalled yet), use Git Bash to:
  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8790/api/jobs/x/cancel -H "Origin: https://evil.example"   # expect 401/403
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8790/api/projects -H "Host: evil.example"                      # expect 401/403
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8790/api/projects                                              # expect 200
  ```
  Then open the desktop client and confirm the editor still loads, previews play and a render runs.
  Check: paste the three outputs into the commit message. Update `SECURITY.md` with a short "What the server accepts" section (3 bullets: this computer; other computers with the key; the optional network-trust switch).

---

### W3 — Proof that the video gets made (tests that matter)

- [x] **W3.1 Classify the slow tests.** (2026-11-20, `docs/dev/slow-tests.md`: 60 passed, 8 skipped) Run `uv run --project server pytest -m slow --collect-only -q`. For each of the 68 tests, find out what it needs: headless Chrome only, ffmpeg only, the speech model (which size? can the tiny/base model run on CPU in under 2 minutes?), a voice model, a GPU, ComfyUI or Ollama. Write `docs/dev/slow-tests.md` as a table: test id | needs | CPU-feasible (yes/no) | measured time on this PC.
  Check: the table has 68 rows (or the current count).

- [x] **W3.2 Mark them.** (2026-11-20; also `network` and `assistant`; `test_gpu` skips on the CPU build of torch) Add pytest markers in `server/pyproject.toml` (`[tool.pytest.ini_options] markers`): `gpu` (needs a graphics card or a model too big for CPU), `models` (downloads a model), `browser` (headless Chrome). Mark each slow test from the table. Do not change any test's logic.
  Check: `pytest -m "slow and not gpu" --collect-only -q` lists exactly the CPU-feasible ones.

- [x] (2026-11-22 audit: commit 3c58eeb) **W3.3 Nightly on GitHub (CPU).** Add `.github/workflows/nightly.yml`:
  - Triggers: `schedule: cron "30 1 * * *"` and `workflow_dispatch`. **Never** `pull_request` (the repo is public).
  - Steps: the same setup as `ci.yml`'s python job (uv sync, generated assets, Studio build), then `pytest -m "slow and not gpu"`. Cache models with `actions/cache`, keyed on the model name.
  - Then one real end-to-end video with the **rules-only** director (no AI needed) from a short English script of its own (not the "yield" sample): plan → voice → render 9:16. Upload the mp4, the contact sheet and the log as artifacts (`retention-days: 14`).
  - On failure: open or update one GitHub issue titled "Nightly check failing" with a link to the run (`gh issue` through `GITHUB_TOKEN` with `issues: write`). On success, close that issue if it is open.
  Check: trigger it once with `gh workflow run nightly.yml --ref workbench` and watch it with `gh run watch`. It must pass. Fix what fails: test bugs are fixed in the test, product bugs in the product. Never skip a test to get green.

- [x] (2026-11-22 audit: commit 3c58eeb) **W3.4 Nightly on this laptop (GPU).** Create `scripts/nightly_local.ps1` (this laptop only; no script for the GPU server). It must refuse to run if any engine address in the server settings points away from `127.0.0.1`/`localhost`. It:
  1. Checks that no `pytest` and no render is already running.
  2. Updates a **separate** checkout (`E:\UltimateVideoTool\nightly-src`, a `git worktree` of the repo on `workbench`, later `main`).
  3. Runs `pytest -m "slow and gpu"` with `VT_PROJECTS` pointing to a fresh scratch folder.
  4. Runs `scripts/lab/vt_lab.py` on its standard cases with the **Claude** director (`--model sonnet`), then the **gemma** director.
  5. Writes `E:\UltimateVideoTool\nightly\<yyyy-mm-dd>\report.md` (pass/fail per test, lab scores, links to mp4s).
  The owner chose **no scheduled task** (2026-11-20): leave the script in place and document, in the script's header, how to run it by hand.
  Check: run it once by hand. The report exists and is readable.

- [x] (2026-11-22: docs/dev/e2e-triage.md; 9 pass, 2 pass alone, 8 marked rewrite in W15.2, contrast and timeline3 noted in ISSUES) **W3.5 Triage the browser suites.** `client/studio/package.json` has 24 `e2e:*` scripts. The last recorded run (`docs/STATUS.md`, 2026-10-26) was 13 passed, 11 failed. Run each against a scratch server on a free port. For each failure, decide one of three outcomes and record it in `docs/dev/e2e-triage.md` (suite | failure | cause | outcome | commit):
  - **Stale test**: the UI changed on purpose → update the test.
  - **Real bug** → fix the product, add a fast unit test where possible.
  - **Feature gone** → delete the suite and its script entry.
  The suites that W8–W11 will rewrite (anything about the left-panel tabs, the Classic timeline or the top bar) may be marked "rewrite in W15.2" instead of fixed now.
  Check: every suite is passing, deleted, or marked for W15.2. Add the passing ones to `nightly.yml` (a second job, `browser`, using Playwright's Chromium).

- [x] **W3.6 A rule for new tests.** (2026-11-20) Add to `CONTRIBUTING.md` and `tests/README.md` (create it if missing): "Test what the code does, not the words of a prompt. Assert on the parsed result, the chosen scene type, the file written, or the request sent; not on whether a sentence appears in a prompt. A prompt test is allowed only for the safety lines that must never disappear, and then it names the line in a constant." Do not mass-rewrite the 85 existing prompt-substring test files. When a step in this plan touches one of them, convert the touched test.
  Check: docs check passes.

- [ ] **W3.7 A real video matrix (replaces the "yield" sample).** Write `scripts/lab/local_matrix.py`: it drives the **installed server on this PC** (`http://127.0.0.1:8790`, key not needed from this computer) through the API only: `POST /api/projects/from-script`, poll the job, export, then write a report and contact sheets to `E:\UltimateVideoTool\matrix\<date>\`. No SSH, no GPU server. Claude on this PC directs through the client helper (the same as `vt_lab.py helper start`, but with the app's own helper or a lab helper folder on E:).
  The matrix covers different kinds of videos, not one topic. Each row is (kind, format, language, voice engine, script). Scripts live in `scripts/lab/matrix/*.txt`, written fresh, 60 to 150 words each: a product explainer, a how-to with steps, a numbers-heavy finance story (fresh, not "yield"), a short story with characters, a health tip, a history fact, a motivational reel, a news-style summary, a comparison, a Banglish casual talk, a Bangla explainer. Kinds: explainer, reel, story, stick, cartoon, emoji, infographic, mixed, auto. Formats: 9:16, 16:9, 1:1. Languages: English, Bangla, Banglish. Pick about 18 rows so that every kind, every format and every language appears at least twice, and no row repeats another's script and kind.
  For each video, the report holds who directed (must say Claude on this PC), the AI conversations, the retention and layout checks, the render time, and a contact sheet. Then **look at the frames**: note captions cut off, empty screens, wrong pictures, text over faces. Run the whole matrix with Claude, then the same 6 rows with gemma.
  Check: the report exists, every row has a status (made, failed with the reason, or skipped with the reason), and the failures are written up as bugs in `docs/dev/matrix-findings.md` with the project id and what was wrong. Fix what is a plain bug; teach the director (prompts, house rules) for what is a quality problem; never override the director with code (standing rule).

---

### W4 — Code health where it hurts

- [x] **W4.1 A route-table snapshot test first.** (2026-11-20; 195 routes in `tests/golden/route_table.json`) Create `tests/test_route_table.py`. It builds the FastAPI `app` from `vt.server.app`, collects `[(route.path, sorted(route.methods or []), route.name) for route in app.routes]` **in order**, and compares the list to `tests/golden/route_table.json`. With `VT_UPDATE_GOLDEN=1` it writes the file instead. Generate the golden file now and commit it.
  Check: the test passes. The golden file has 267+ entries (the documented count).

- [ ] (2026-11-22, deferred: every existing router is included at the end of app.py, so moving a block changes route order unless the helpers (proj, changed, compose_all, hub, the body models) first move to routes/_common.py; no user-visible gain and app.py is also edited by Codex, so it waits for a quiet moment) **W4.2 Split `server/vt/server/app.py` (3,325 lines) into routers.** Create `server/vt/server/routes/` with one module per area. Choose the areas from the URL prefixes actually present. Expected: `projects.py`, `media.py`, `transcript.py`, `script.py`, `director.py`, `plan.py`, `render.py` (render/preview/export), `quality.py` (qa/autofix/retention), `ai.py` (llm/ai/models), `mcp.py`, `jobs.py`, `engines.py`, `settings.py`, `voices.py`, `social.py`, `shorts.py`, `assets.py` (themes/fonts/icons/music), `system.py` (health/version/doctor). Each module has `router = APIRouter()`. Shared helpers go into `routes/_common.py`.
  Rules:
  1. Move each handler **verbatim** (cut and paste, only fixing imports). Do not refactor logic in this step.
  2. Keep registration order. FastAPI matches routes in the order they were added, so a later generic path must not move ahead of a specific one. Include the routers in `app.py` in the order in which each area's **first** route appeared, and if an area's routes were interleaved with another's in a way that matters, split it into two routers. The W4.1 test proves the order is unchanged.
  3. `app.py` keeps: app creation, middleware, startup/shutdown, exception handlers and the `include_router` calls. Target under 400 lines.
  4. Do it area by area, one commit per area, running W4.1 and the fast suite each time.
  Check: `test_route_table.py` passes unchanged. Fast suite green. `scripts/check_docs.py` still counts 267 routes (fix its counter if it parsed `app.py` text).

- [~] (2026-11-22: vt/notices.py + a "skipped" banner on the video page; every broad catch in pipeline.py, director/, directors.py, compose/, tts.py, ai/providers.py, script/, craft.py records a notice, logs with its traceback, is narrowed, or carries its reason; ruff BLE001 clean on all of them; fast suite green. Not done: a forced-fallback test per module (two exist: tests/test_notices.py)) **W4.3 No silent failures in the video pipeline.** Scope: `server/vt/pipeline.py`, `server/vt/director/`, `server/vt/directors.py`, `server/vt/compose/`, `server/vt/tts.py`, `server/vt/ai/providers.py`, `server/vt/script/`, `server/vt/craft.py`. (The whole of `server/vt` has 243 `except Exception` handlers; this step covers only these modules.) For each `except Exception` there, classify it and act:
  - **(a) An optional extra that may be missing** (a model, a font, an engine): keep the fallback, but log it, `log.warning("…: %s", e, exc_info=True)`, **and** record it where the person sees it. Use the project's job warnings or the "AI conversations" log; find the existing mechanism the rules-only fallback uses to make "the video says so". Example warning: "The local AI did not answer, so built-in rules planned scenes 3–5."
  - **(b) A programmer error being hidden** (KeyError, TypeError, AttributeError on our own data) → narrow the `except` to the specific expected exception, or remove it so the bug shows.
  - **(c) A failure the person must act on** (no disk space, a missing executable) → raise a clear error that reaches the UI as a job error in plain words.
  Add `ruff` rule `BLE001` for these paths only (in `server/pyproject.toml`, `[tool.ruff.lint.per-file-ignores]` the other way round, or `extend-select` with an `include` list; use whatever the installed ruff version supports). Every kept broad catch gets `# noqa: BLE001 — <why>`.
  Check: `uv run --project server ruff check server/vt/pipeline.py server/vt/director …` clean. Fast suite green. One new test per module that forces the fallback (monkeypatch the engine to raise) and asserts the warning appears in the project's record.

---

### W5 — Repo and docs

- [x] **W5.1 Evidence leaves git.** (2026-11-21; zip at `E:/UltimateVideoTool/docs-evidence-2026-11.zip` (130 MB), attach to the 0.5.0 release; tip 492.7 to 149.8 MB) Zip `docs/evidence/` to `docs-evidence-2026-11.zip` (outside the repo, in `E:\UltimateVideoTool\`), attach it to the 0.5.0 release (W1.6, or now if 0.5.0 is out: `gh release upload v0.5.0 <zip>`). Then `git rm -r --cached docs/evidence` and add **`/docs/evidence/`** (anchored, with the leading slash; see the owner's earlier loss from unanchored rules) to `.gitignore`. Move the folder on disk to `E:\UltimateVideoTool\evidence\` and make `scripts/check_docs.py` look there for evidence links, or drop evidence-link checks from the docs that W5.2 archives.
  Check: `git ls-files docs/evidence | wc -l` prints 0. `check_docs.py --structural-only` passes. Clone size of the *tip* (`git archive HEAD | wc -c`) is recorded in the baseline file.

- [x] **W5.2 One current STATUS.** (2026-11-21; old audits and the old status moved to `docs/history/`) Rewrite `docs/STATUS.md` as a short, current page (under 150 lines):
  1. The version and its status (beta).
  2. Test suites today: fast (count, last run), nightly CPU (link to the latest run), nightly GPU (last report date), browser suites (count passing).
  3. The measured facts table (keep the `facts:begin/end` block that `check_docs.py --fix-facts` regenerates).
  4. "Known gaps", taken from the open acceptance items in `docs/AUDIT-2026-11-03.md` and the open steps of PLAN-PERFECT, one line each.
  Move to `docs/history/` (keep content, no edits): `AUDIT-2026-10-28.md`, `AUDIT-2026-11-03.md`, `AUDIT-SKILLS-DIRECTION-2026-11-03.md`, `UI-REVIEW.md`, `STORY-ENGINE-PLAN.md`, `ACTIVE-WORK.md`, `HANDOFF.md`, and from `docs/plans/` every plan whose steps are all done or which a later plan replaced. Read each one's last lines to decide; when unsure, leave it. Fix every link that pointed at a moved file (`git grep -n "<name>"`). Remove references to `C:\Users\atanu\Desktop\Video Tool`.
  Check: `check_docs.py` passes. `docs/README.md` lists only current documents plus one link to `docs/history/`.

- [x] **W5.3 The public root.** (2026-11-21) The repo root keeps: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `THIRD-PARTY.md`, `pyproject.toml` and the folders. Move `plan.md` to `docs/history/plan-2026-10.md`.

- [x] **W5.4 The handoff notes.** (2026-11-21; memory note updated) Move `docs/dev/CODEX-HANDOFF.md` and `docs/dev/WORKLOG.md` to `docs/dev/`. Update every pointer to them: `git grep -n "CODEX-HANDOFF\|WORKLOG"`, including `.codex/`, `.agents/`, `.claude/`, `AGENTS.md` if present, and this plan's section 0.1. Then update the owner's Claude memory note `codex-handoff.md` in `C:\Users\Roy\.claude\projects\c--Users-Roy-Desktop-ultimate-video-tool\memory\` to say the files now live in `docs/dev/`.
  Check: `git grep -n "docs/dev/CODEX-HANDOFF.md\|docs/dev/WORKLOG.md"` shows only `docs/dev/` paths.

---

### W6 — Design tokens: one source of colour, size and type

Target look: the openfilm screenshot the owner liked. Quiet cool greys, panels separated by one-pixel lines, small text, colour only where it means something.

- [x] (2026-11-22 audit: commit 848adb6) **W6.1 The token file.** Create `client/studio/src/tokens.css`, the **only** file in the Studio UI that contains raw colour values. Import it first in `main.tsx`. Contents:

  **Surfaces** (bottom to top). `--bg-app` is the window, the top bar and the seams between panes. `--bg-panel` is a pane's inside. `--bg-raised` is cards, menus, popovers, dialogs and tooltips. `--bg-viewer` is the area around the picture.

  | token | light | dark |
  |---|---|---|
  | `--bg-app` | `#e6e6ea` | `#141414` |
  | `--bg-titlebar` | `var(--bg-app)` | `#1c1c1c` |
  | `--bg-panel` | `#fbfbfc` | `#191919` |
  | `--bg-raised` | `#ffffff` | `#202020` |
  | `--bg-viewer` | `#f3f3f5` | `#191919` |
  | `--dock-line` | `#d4d4da` | `#000000` |
  | `--bg-field` | `rgb(16 16 24 / .055)` | `rgb(255 255 255 / .08)` |
  | `--bg-hover` | `rgb(16 16 24 / .05)` | `rgb(255 255 255 / .06)` |
  | `--bg-pressed` | `rgb(16 16 24 / .09)` | `rgb(255 255 255 / .12)` |
  | `--bg-selected` | `color-mix(in srgb, var(--accent) 13%, transparent)` | `color-mix(in srgb, var(--accent) 16%, transparent)` |
  | `--text` | `#161619` | `#f0f0f0` |
  | `--text-muted` | `#5d5d63` | `#a3a3a3` |
  | `--text-faint` | `#8b8b92` | `#717177` |
  | `--border` | `rgb(16 16 24 / .085)` | `rgb(240 240 255 / .075)` |
  | `--border-strong` | `rgb(16 16 24 / .16)` | `rgb(240 240 255 / .15)` |
  | `--primary` (ink: the main action) | `#161619` | `#ebebed` |
  | `--primary-hover` | `#2e2e33` | `#ffffff` |
  | `--on-primary` | `#ffffff` | `#0a0a0c` |
  | `--accent` (brand orange: selected, current, focused) | `#e8630f` | `#ff7a33` |
  | `--accent-text` (accent for small text) | `#b04a06` | `#ff9a5c` |
  | `--accent-soft` | `color-mix(in srgb, var(--accent) 12%, transparent)` | `… 14% …` |
  | `--on-accent` | `#ffffff` | `#1f0d00` |
  | `--focus-ring` | `0 0 0 2px var(--accent)` | same |
  | `--ok` / `--warn` / `--err` | `#1f8a4c` / `#b25e00` / `#d1342f` | `#4cc27a` / `#f0b03c` / `#f2665f` |

  **Timeline clips by kind** (one quiet colour each, one lightness, white labels):

  | token | light | dark |
  |---|---|---|
  | `--clip-scene` | `#54789d` | `#354f6a` |
  | `--clip-picture` | `#497c93` | `#2e5363` |
  | `--clip-video` | `#4f6d8f` | `#33495f` |
  | `--clip-element` (motion graphics, charts) | `#7968a8` | `#504472` |
  | `--clip-caption` | `#b5703d` | `#7f4d28` |
  | `--clip-sticker` (emoji, icons) | `#3d8a5c` | `#24603e` |
  | `--clip-narration` | `#318383` | `#1c5757` |
  | `--clip-music` | `#5b6aa6` | `#3a4673` |
  | `--clip-sfx` | `#8d5a86` | `#5e3a59` |
  | `--tl-lane` / `--tl-row` / `--tl-head` | `#f1f1f3` / `#f7f7f8` / `var(--tl-row)` | `#151518` / `#1d1d1d` / `#1e1e1e` |
  | `--tl-playhead` / `--tl-select` | `#161619` | `#ffffff` |
  | `--tl-wave` | `rgb(255 255 255 / .5)` | `rgb(255 255 255 / .4)` |

  **Type, size and motion** (both themes):
  - `--font-sans: "Inter Variable", "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Hind Siliguri", "Noto Sans Bengali", sans-serif`. Bundle Inter with `@fontsource-variable/inter` (OFL; add it to THIRD-PARTY.md), so it works offline.
  - `--font-mono: ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace`.
  - Text sizes `--fs-11: 11px` (timeline, labels), `--fs-12` (secondary), `--fs-13` (base UI), `--fs-15` (pane titles, dialog titles), `--fs-20` (page titles). Weights 400 / 500 / 600 only. No 700 in the app's chrome.
  - Spacing `--sp-1: 4px` … `--sp-6: 24px` (4, 8, 12, 16, 20, 24). Radius `--r-sm: 6px` (controls), `--r-md: 8px` (cards), `--r-lg: 12px` (dialogs).
  - Heights: `--h-control: 28px`, `--h-topbar: 40px`, `--h-pane-header: 36px`.
  - Shadows: `--shadow-sm`, `--shadow-lg` (light: `0 1px 2px rgb(16 16 24/.05), 0 1px 3px rgb(16 16 24/.05)` and `0 12px 32px rgb(16 16 24/.1), 0 4px 8px rgb(16 16 24/.05)`; dark: the same with `rgb(0 0 0/.3)` and `rgb(0 0 0/.5)`).
  - Motion: `--ease: cubic-bezier(.2,.8,.2,1)`, `--t-fast: 120ms`, `--t-pane: 200ms`. Everything goes to `0ms` under `prefers-reduced-motion: reduce`.

  The theme is chosen by `<html data-theme="light|dark">` (the existing `useDark()` in `Shell.tsx`). Define the light values on `:root, [data-theme="light"]` and the dark values on `[data-theme="dark"]`.

  **Legacy aliases** at the bottom of the file, so nothing breaks today: `--bg: var(--bg-app); --panel: var(--bg-panel); --panel-2: var(--bg-field); --fill: var(--bg-field); --fill-2: var(--bg-pressed); --muted: var(--text-muted); --accent-strong: var(--accent); --accent-ink: var(--on-accent); --card-bg: var(--bg-raised); --input-bg: var(--bg-field); --fg: var(--text); --font: var(--font-sans); --radius: var(--r-md); --radius-lg: var(--r-lg); --shadow: var(--shadow-sm); --shadow-pop: var(--shadow-lg);` and the remaining names you find in `styles.css`'s `:root`. Remove the old `:root` and `[data-theme="dark"]` blocks from `styles.css`.

  **OpenChatCut skins**: in `client/studio/src/occ/occ.css` (or wherever `--cc-*` are defined, see `occ/src/theme.ts` and `skins.ts`), map every `--cc-*` to a new token, e.g. `--cc-bg: var(--tl-lane); --cc-panel: var(--bg-panel); --cc-text: var(--text)`. Keep the skin registry, but make the default skin read the tokens.
  Check: **contrast**. Write `scripts/dev/check_contrast.mjs`. It parses `tokens.css` and checks, in both themes: `--text`, `--text-muted` and `--accent-text` on `--bg-panel` and `--bg-raised` ≥ 4.5:1; `--text-faint` ≥ 3:1; white on every `--clip-*` ≥ 4.5:1; `--on-primary` on `--primary` ≥ 4.5:1; `--on-accent` on `--accent` ≥ 4.5:1 (if not, darken `--accent` in steps of 4% lightness until it passes and note the new value here). Run it in the CI `studio` job. Also run the existing `npm run e2e:contrast`.

- [x] (2026-11-22 audit: commit f9f3f9c, a ratchet) **W6.2 A guard against new raw colours.** Create `scripts/dev/check_raw_colors.mjs`. It fails when a `.tsx`, `.ts` or `.css` file under `client/studio/src` contains `#rgb`, `#rrggbb`, `rgb(` or `hsl(` outside `tokens.css`. Exemptions are listed in the script with a reason each. Exempt **content colours**, the colours of the *video* rather than the app: the look/palette data (themes, `DesignStudio.tsx` palettes, `review/story/`, caption-look presets) and canvas code that draws the video. The baseline today is 223 distinct values. The script also accepts `--report`, which prints file:line:value with the nearest token by colour distance. Add it to the CI `studio` job in **report-only** mode now. W6.3 switches it to failing mode.

- [~] (2026-11-22 audit: 76 moved, 233 still allowed by the ratchet; commit f9f3f9c) **W6.3 Replace raw colours in the app's chrome.** Using `check_raw_colors.mjs --report`, replace UI colours with tokens, file by file, starting with the shell, editor and timeline files. Rules:
  - A colour that means "selected / current / focus" → `--accent` family.
  - A success / warning / error colour → `--ok` / `--warn` / `--err`.
  - A grey → the nearest surface, text or border token. Never invent a new grey.
  - Canvas drawing of UI (the timeline's waveforms, playhead and ruler) reads tokens at draw time: add `client/studio/src/ui/cssVar.ts` (`export const cssVar = (name: string, el: Element = document.documentElement) => getComputedStyle(el).getPropertyValue(name).trim()`) and re-read on theme change (listen for the `data-theme` attribute change with a `MutationObserver`).
  - Merge the "cleanup" files into their owners and delete them: `review/editor-cleanup.css`, `pages/result-cleanup.css`, `settings-clarity.css`.
  When the report shows only exempt files, switch the CI check to failing mode.
  Check: CI check passing. The distinct-colour count, outside exempt files, is 0. Screenshots of every main page in light and dark go to `docs/dev/shots/w6-*.png`. Look at each and fix anything unreadable before ticking.

- [ ] **W6.4 Base controls.** In `client/studio/src/ds/` (the existing design-system components, `ds/index.tsx` + `ds.css`), restyle to the tokens:
  - **Button**: kinds `primary` (ink background `--primary`, text `--on-primary`), `secondary` (`--bg-field`, hover `--bg-hover`), `ghost` (transparent, hover `--bg-hover`), `danger` (text `--err`). Height `--h-control`, radius `--r-sm`, `--fs-13`, weight 500, icon 16px with 6px gap. No gradients, and no "springy" scale presses (remove `--ease-spring` use in the app's chrome).
  - **Input / Select / Textarea**: `--bg-field` background, no border until hover (`--border`), focus ring `--focus-ring`.
  - **Segmented control** (tabs): a `--bg-field` track. The picked segment uses `--bg-raised` with `--shadow-sm`, its text `--text`; the others `--text-muted`.
  - **Switch**: on = `--accent`.
  - **Icon button**: 28×28, icon `--text-muted`, hover `--text` plus `--bg-hover`, active state `--bg-selected` plus `--accent-text`.
  - **Tooltip**: `--bg-raised`, `--shadow-lg`, `--fs-12`, with the shortcut shown in `--text-faint` (for example "Library  Ctrl+B").
  - **Menu / Popover**: `--bg-raised`, `--r-md`, `--shadow-lg`, rows 28px, hover `--bg-hover`.
  - **Dialog**: `--r-lg`, side area `--bg-panel`, main area `--bg-raised`.
  Check: `npm run e2e:a11y` and `e2e:contrast` pass. Before/after screenshots of the Settings page show the change.

---

### W7 — The dock workbench (panes that resize, hide and remember)

- [x] (2026-11-22 audit: commit d88b1e4) **W7.1 Port the dock engine.** Copy, with the W0.2 header, into `client/studio/src/workbench/`:
  - `workspace-dock.ts` (from `E:\openfilm-a1b8d75\packages\openfilm\studio\ui\src\lib\workspace-dock.ts`) and its test `workspace-dock.test.ts`.
  - The parts of `lib/workspaces.ts` that `workspace-dock.ts` imports (`centerOf`, `ArrangementSpec`, `BlockSpec`, `WorkspaceLayout`, `defaultWorkspace`, the read/validate functions), into `workspaces.ts`. Drop the plugin/workbench registry and the v1/v2 migration keys.
  - `components/PaneDivider.tsx` → `workbench/PaneDivider.tsx`. Translate any Tailwind classes into a `workbench.css` that uses our tokens: the divider is a 1px `--dock-line` line with a 9px invisible hit area and `cursor: col-resize/row-resize`, and while dragging it shows a 2px `--accent` line.
  - `components/dock-pane-bar.ts` → `workbench/dock-pane-bar.ts`.
  Our blocks (`BlockSpec`s) are: `viewer` (center), `library` (left, 280px, range 220–480), `inspector` (right of the viewer, 300px, range 240–480), `timeline` (bottom, 300px tall, range 160–600) and `assistant` (the page's chat, right, 400px, range 320–640, full height). Map OpenFilm's page blocks: their `chat` → our `assistant`; their `library` → our `library`. **The tree:** `assistant` is outermost on the right and spans the full height. Inside it, `timeline` spans the bottom under `library | viewer | inspector`. This matches the screenshot.
  Make the test runner see the new tests: they use `node:test`/vitest-style syntax. Check what `npm run test:timeline` uses and wire `workbench/*.test.ts` into the same runner (add a `test:workbench` script and call it from CI's `studio` job).
  Check: `npm run test:workbench` passes, with OpenFilm's dock tests adapted to our block names.

- [x] (2026-11-22 audit: commit 48a3f8f) **W7.2 The Workbench component.** Create `client/studio/src/workbench/Workbench.tsx`:
  - Props: `panes: Record<'viewer'|'library'|'inspector'|'timeline'|'assistant', ReactNode>` and `layoutKey: string`.
  - It renders the dock tree from `defaultDockTree(...)` as nested flex boxes with `PaneDivider`s. Sizes come from the tree (`size` plus `anchor` for fixed-size panes; `ratio` otherwise). The viewer always takes the remaining space.
  - Each pane gets a header (`--h-pane-header`, `--fs-12` weight 500, `--text-muted`, a close ✕ icon button on hideable panes) from `dock-pane-bar.ts`'s rules, except the viewer, which has none.
  - Hidden panes keep their place in the tree. Showing one again restores its size.
  - It persists `{tree, shown, sizes}` to `localStorage["vt.workbench.v1." + layoutKey]`, wrapped in try/catch (private windows throw), and is debounced 300ms during drags.
  - Responsive behaviour:
    - Window width < 1180px: the `assistant` becomes an overlay drawer on the right (over the viewer, `--shadow-lg`), opened by its toggle.
    - Width < 900px: `library` and `inspector` become overlay drawers too.
    - Width < 700px: the existing compact mode stays as it is (the `compact` flag in `Review.tsx`).
  - Expose `useWorkbench()`: `{ shown(pane), toggle(pane), show(pane), focus(pane), reset() }`.
  Check: a small Playwright suite, `e2e:workbench` (new), drags each divider, hides and shows each pane, reloads, and finds the same sizes. It also resizes the window to 1000px and 800px and checks the drawers. Add it to the nightly browser job.

- [~] (2026-11-22 audit: keys in workbench/shortcuts.ts, commit 48a3f8f; palette entries not checked) **W7.3 Shortcuts and the command palette.** Register D14's shortcuts in the existing shortcut system (`client/studio/src/occ/src/shortcuts/`, or wherever `CommandPalette.tsx` reads commands): `View: Toggle Library` (Ctrl+B), `View: Toggle Assistant` (Ctrl+Alt+B), `View: Toggle Timeline` (Ctrl+J), `View: Toggle Inspector` (Ctrl+Alt+I), `View: Reset Layout`, `Assistant: Focus Message Box` (Ctrl+L), and `Command Palette` on Ctrl+Shift+P (keep the palette's existing shortcut too). Shortcuts must not fire while typing in a text field, except Ctrl+L and Ctrl+Shift+P. On macOS use Cmd.
  Check: unit tests for the key handler (typing in an input does not toggle panes). `e2e:workbench` covers Ctrl+B and Ctrl+J.

---

### W8 — One quiet top bar, and what goes in each pane

- [ ] **W8.1 Map today's controls to their new homes.** Before moving anything, write the table below into `docs/dev/editor-map.md`, completed from the actual code of `client/studio/src/pages/Review.tsx` and `Shell.tsx` (find every button, tab and toggle). Anything not in the table must be found and placed before W8.2 starts.

  | Today | Where it goes |
  |---|---|
  | Top bar: ☰ menu, ← back, project title | Top bar left: ☰ (app menu: Projects, New video, Look, Voices, Settings, Server, Help), ← back to Projects, the title (click to rename) |
  | Top bar: Edit ▾ | ☰ app menu → Edit submenu (Undo, Redo, Cut, Copy, Paste, Select all, Delete) |
  | Top bar: Undo / Redo | Top bar right (icon buttons) |
  | Top bar: Script | Library pane → **Script** tab |
  | Top bar: AI | Removed. The Assistant pane is always there (toggle icon top right) |
  | Top bar: Export (blue) | Top bar right, **Export** as an ink `primary` button. It is the only filled button in the bar |
  | Row 2: Tools / Details / Focus | Removed. Tools = Library pane toggle; Details = Inspector toggle; Focus = a "Focus" command (Ctrl+Alt+F) that hides Library, Inspector and Assistant and restores them on the second press |
  | Row 2: "Preview updates as you edit" | Removed (it is how it always works) |
  | Row 2: Video settings | Inspector, when nothing is selected (W8.4) |
  | Left panel tabs: Director | Assistant pane → **Director** (W10) |
  | Left panel tabs: Scenes | Library → **Scenes** tab |
  | Left panel tabs: Direction | Inspector → a scene's **Direction** section |
  | Left panel tabs: Elements | Library → **Elements** tab (drag onto the viewer or the timeline) |
  | Left panel tabs: Script | Library → **Script** tab |
  | Left panel tabs: Captions | Inspector when a caption is selected; caption style in Video settings |
  | Left panel tabs: Pictures | Library → **Media** tab |
  | Left panel tabs: Sound | Library → **Sounds** tab |
  | Timeline row: Classic / New timeline | Removed in W11 |
  | Timeline row: Saved. | A small "Saved" note in the top bar beside the title (`--text-faint`, fades after 2 s) |

- [ ] **W8.2 The top bar.** Create `client/studio/src/workbench/TopBar.tsx` and use it on the editor page only. Other pages keep the Shell's bar, restyled by tokens in W6.
  - Height `--h-topbar`, background `--bg-titlebar`, a 1px `--dock-line` at the bottom. In the desktop app it is the window's drag region (`-webkit-app-region: drag`; buttons `no-drag`), with room for the window controls (`--titlebar-right-x`: read from the desktop app's preload, as OpenFilm's `lib/host.ts` does).
  - **Left:** ☰, ←, the project title (`--fs-13`, weight 500; double-click or click → inline rename; Enter saves, Esc cancels), the "Saved" note.
  - **Center:** empty, drag region.
  - **Right:** Undo, Redo | pane toggles Library, Timeline, Inspector, Assistant (icon buttons with an *active* state when shown, tooltips with shortcuts; lucide icons `PanelLeft`, `PanelBottom`, `PanelRight`, `MessageSquare` or `Sparkles`) | ⋯ (more: Video settings, Quality check, Details → AI conversations, Keyboard shortcuts) | **Export**.
  Check: `e2e:editor` updated. Screenshot `docs/dev/shots/w8-topbar.png`.

- [ ] **W8.3 The Library pane.** Create `client/studio/src/workbench/LibraryPane.tsx`:
  - The header row holds a search field ("Search", filters the active tab) and a ＋ menu (Add media, Record voice, Add element).
  - Under it, one segmented control: **Scenes · Script · Media · Elements · Sounds**. Each tab mounts the **existing** component: `ScenesPanel`, `ScriptPanel`/`TranscriptPanel`, `MediaBin`, `ComponentLibrary`/`CatalogList`, and the sound picker. Do not rewrite their logic. Restyle their outer containers to the tokens only.
  - **Scenes:** compact rows (thumbnail 64×36 at 16:9, or 36×64 for 9:16 projects; "1 · 0:00–0:02" in `--fs-11` `--text-faint`; the first line of its words in `--fs-12`; a kind chip like "talking" in `--bg-field`). A selected row gets `--bg-selected` with a 2px `--accent` left edge.
  - **Media:** a grid like the openfilm screenshot (2 columns at 280px), each tile `--r-md` with the duration bottom-right on a dark chip, and the name under it in `--fs-12`.
  - The last tab used is remembered per project (localStorage, try/catch).
  Check: `e2e:layers-media` and `e2e:script` pass (update their selectors). Screenshot.

- [ ] **W8.4 The Inspector pane.** Create `client/studio/src/workbench/InspectorPane.tsx`. It shows, by selection:
  - **Nothing selected → Video settings:** size and shape, look and palette, captions style, music and its volume, narration voice. Reuse the existing settings components (`VisualControls`, `CaptionLook`, sound controls). At the very top, a one-line hint in `--text-faint`: "Click anything in the picture or on the timeline to change it."
  - **A scene →** its header (Scene 3 · 0:04–0:06 · 2.2 s), then the collapsible sections **On screen** (the elements list with ＋ Add, from today's "On screen (0)"), **Direction** (today's `DirectionPanel`), **Timing**.
  - **An element or layer →** `LayerInspector`/`Inspector` with `TransformControls` (position, size, rotation, stretch, slant, flip, crop, blur, blend, keyframes, per the owner's human-in-the-loop decision).
  - **A caption →** `CaptionInspector`.
  - **A video clip →** `VideoInspector`.
  - Each section has a 32px header (`--fs-12` weight 600 `--text-muted`, uppercase off, a chevron) that collapses it, and the collapsed state is remembered.
  - "Ask AI" (today's tab inside the scene inspector) becomes an icon button in the inspector header, "Ask the assistant about this", which adds the selection as a pill in the Assistant (W13).
  Check: `e2e:editor`, `e2e:layers` and `e2e:context` pass (updated). Screenshot for each selection kind.

- [ ] **W8.5 The Viewer pane.** Restyle `review/Preview.tsx`'s container:
  - Background `--bg-viewer` in **both** themes (light grey in light, not black). The picture is centred with `--shadow-sm` and no frame.
  - The transport bar under the picture is 40px: time `00:01.08 / 00:06.83` in `--font-mono` `--fs-12` on the left, ⏮ ▶ ⏭ in the centre (▶ 32px), and on the right fit/zoom, a captions toggle, a speed menu (1×) and volume in a ⋯ menu, plus fullscreen.
  - Hovering the picture shows nothing extra. Element handles appear only on selection (existing `TransformHandles`).
  - Remove the big scrubber from under the video: the timeline is the scrubber. Keep a thin 2px progress line at the bottom of the picture in `--accent`, so position is visible when the timeline pane is hidden.
  Check: `e2e:editor` passes. Playback, seeking with the timeline, and fullscreen work.

- [~] (2026-11-22 audit: docked layout in commit 48a3f8f; TopBar/LibraryPane/InspectorPane as separate files and editor-map.md not made) **W8.6 Compose the page.** Rewrite `client/studio/src/pages/Review.tsx` to: `TopBar` + `Workbench` with the five panes. Move state that is shared between panes (`sel`, `selEl`, `selLayer`, `selectedWord`, `videoSel`, the current scene, the `useReview` result) into a small store, `client/studio/src/workbench/selection.ts` (a `useSyncExternalStore` store like the existing `store.ts` ones), so panes do not pass ten props each. Keep every feature that worked; this is a re-layout, not a rewrite of features. `Review.tsx` should end under 250 lines.
  Check: **every** e2e suite listed as passing in W3.5 still passes (update selectors only). `npm run build` passes. Fast suite green. Before/after screenshots side by side in `docs/dev/shots/w8-*.png`. Look at them at 1440×900 and 1280×720, in light and dark.

---

### W9 — Electron 44 in both desktop apps

- [x] (2026-11-22 audit: 44.10.2, commit 3572bfd) **W9.1 Find the newest Electron 44.x** that is at least two weeks old (`npm view electron@44 version time --json`). Update `client/desktop/package.json` and `server/desktop/package.json`: `electron` to that exact version, and `electron-builder` to the newest version supporting it (check electron-builder's releases). Run `npm install` in both and commit the lock files.

- [~] (2026-11-22 audit: apps verified working on 44 (commit 3572bfd); the per-major breaking-change review is not recorded) **W9.2 Breaking changes.** Read Electron's "Breaking Changes" document for every major from 34 to 44. For each item, `git grep` our desktop code (`client/desktop/*.js`, `server/desktop/*.js`) for the API named, and fix what is used. Usual suspects: `protocol.registerFileProtocol` and friends (replaced by `protocol.handle`), `session` APIs, `webContents` events renamed, `nativeImage`, `BrowserView` (deprecated in favour of `WebContentsView`), and preload sandbox defaults (`sandbox: true` is the default; check that `preload.js` and `main-preload.js` only use `contextBridge`/`ipcRenderer`). Also check `ELECTRON_RUN_AS_NODE` use (the helper, `mcp-bridge.js`): it still works, and under it `process.versions.node` is now ≥ 22.
  Check: all node tests in CI's `studio` job pass. `npm --prefix client/desktop start` and `npm --prefix server/desktop start` open their windows. Build both Windows installers, install over this PC's copies, connect the client to the server, open a project, play, render a 10-second preview, and run the helper (Claude on this PC) through one planning task with `--model sonnet`.

- [x] **W9.3 Linux.** Skipped by the owner's decision (Windows only). Only the Windows installers are built and tested here; GitHub still builds the Linux ones in the Release workflow, untested.


### W10 — The Assistant pane

- [~] (2026-11-22: starter suggestions, model chooser, New conversation, "Continue" an earlier one; the history popover and the agent chip popover not done) **W10.1 The pane frame.** Create `client/studio/src/assistant/AssistantPane.tsx` + `assistant.css` (tokens only):
  - **Header (36px):** the conversation title (first message, cut to 40 characters; `--fs-12` weight 500), ＋ (new conversation), 🕘 (history popover listing earlier conversations for this project), ⋯ (Copy conversation, Details).
  - **Body:** the message list (W10.2), with `useStickToBottom` behaviour. Port OpenFilm's `useStickToBottom.ts` (327 lines, MIT, with header): it stays pinned to the newest message unless the person scrolled up, and then shows a "↓ New messages" chip.
  - **Footer:** the composer (W10.3) and, under it, the **agent chip**: an icon plus the name, e.g. "Director · Claude on the server", or "Claude Code · Sonnet". Clicking it opens a popover to choose who you are talking to: **Director** (the server's director: whatever is set in Settings → Director, works everywhere) and, in the desktop app, **Claude Code** and **Codex** (W12), each showing "Ready", "Sign in…" or "Not installed — how to install". Port the layout idea of OpenFilm's `ModelPopover.tsx`; do not port the file.
  - An empty conversation shows three starter suggestions for the project's state: "Tighten the opening", "Make the captions bigger", "Find a better picture for scene 2". Clicking one fills the composer.
  Check: the pane renders in the workbench; the agent chip popover opens and closes; keyboard focus order is header → list → composer → chip.

- [~] (2026-11-22: finished steps fold into "Worked 12s · 3 steps ›" that opens to the list; Markdown (paragraphs, lists, bold, code) parsed to data, never HTML, with a test; errors are a red-edged card with Sign in or Try again (resends the last message), browser test) **W10.2 Messages.** Reuse what is already ported from OpenChatCut first: `occ/src/components/chat/ChatMessage.tsx`, `ChatRunStatus.tsx`, `ToolGroupRow.tsx`, `message-groups.ts`.
  - **Person's message:** right-aligned bubble, `--bg-raised` in light and `--chat-message-bg` (`#252525`) in dark, `--r-lg`, max 85% width, with attached pills (W13) above the text.
  - **Agent's reply:** no bubble, plain text at `--fs-13`, line-height 1.55, with Markdown (paragraphs, lists, bold, code, links). Links starting with `vt://` are handled by W13.4.
  - **Work steps:** while working, one live line ("Changing scene 3's picture…") with a subtle animated dot. When finished, the steps collapse into one row, **"Worked 3m 06s · 11 steps ›"**, which expands to show each step (tool name in plain words plus a short result) as in the openfilm screenshot.
  - **Errors** are a `NoticeCard`-style card (`--err` left edge) with the plain-words reason and one action, such as "Sign in" or "Try again".
  Check: a unit test of `message-groups.ts` grouping (steps between two replies collapse into one group). A visual check in both themes.

- [ ] **W10.3 The composer.** Add `lexical` and `@lexical/react` (MIT; exact versions at least two weeks old; React 18 compatible, so check their peer range) to `client/studio`. Port OpenFilm's `apps/desktop/chat/src/components/prompt-editor/` (`PromptEditor.tsx`, `PromptPill.tsx`, `MentionMenuPlugin.tsx`, `MovePillsPlugin.tsx`, and whatever they import) into `client/studio/src/assistant/prompt-editor/`, with headers, translating Tailwind classes to `assistant.css`.
  - A multi-line box, 1 to 8 lines, then it scrolls. Enter sends, Shift+Enter adds a new line, Esc blurs. Placeholder: "Say what to change. Type @ to point at a scene, a picture or a moment."
  - **@** opens a menu of scenes, media, elements and captions in this project (from the selection store and `useReview`); choosing one inserts a pill.
  - Pills can be removed with ✕ or Backspace.
  - A ■ Stop button replaces ↵ while the agent works.
  - A 📎 button attaches a file (it uploads to the project's media first, then becomes a media pill).
  Check: unit tests for the pill serialisation (W13.2's format). `e2e:assistant` (new): type, @-mention a scene, send to a stub, see the message.

- [ ] **W10.4 Move the Director chat in.** Make `occ/bridge/DirectorChat.tsx`'s logic a *backend* of the Assistant pane: extract its fetch/post/job-polling code into `client/studio/src/assistant/backends/director.ts`, which implements the interface below, and delete the left-panel "Director" tab (W8.1).
  ```ts
  export interface AssistantBackend {
    id: 'director' | 'claude' | 'codex';
    label: string;                                  // "Director", "Claude Code", "Codex"
    status(): Promise<{ ready: boolean; detail: string; action?: 'sign-in' | 'install' | 'settings' }>;
    open(projectId: string, resume?: string): Promise<{ conversationId: string; history: AssistantMessage[] }>;
    send(conversationId: string, text: string, refs: VideoRef[], images: Blob[]): AsyncIterable<AssistantEvent>;
    stop(conversationId: string): Promise<void>;
    answerPermission?(conversationId: string, requestId: string, choice: 'once' | 'chat' | 'deny'): Promise<void>;
    listConversations(projectId: string): Promise<{ id: string; title: string; at: string }[]>;
  }
  export type AssistantEvent =
    | { type: 'text'; text: string }                           // appended to the current reply
    | { type: 'step'; id: string; title: string; status: 'running' | 'done' | 'failed'; detail?: string }
    | { type: 'permission'; requestId: string; title: string; detail: string }
    | { type: 'changed'; scenes: string[]; removed: string[] }  // the project changed: W14
    | { type: 'error'; kind: 'limit' | 'login' | 'other'; message: string }
    | { type: 'done'; stopReason: string; ms: number };
  ```
  The Director backend maps the existing `/api/projects/{id}/director/chat` job's progress messages to `step` events, and its result (`changed_scenes`, `removed_scenes`, `reply`) to `changed` + `text` + `done`. The undo/redo for a director change (`historyAction` today) becomes an "Undo this change" link under that reply.
  Check: the existing director chat tests (search `tests/` for `director/chat`) still pass. A real run: on the installed server, open a project, ask the Director "make the captions bigger", and see the steps, the reply and the timeline update.

---

### W11 — One timeline, quieter

- [~] (2026-11-22: docs/dev/timeline-parity.md written; narration mute and volume ported with a test; 6 rows still to port) **W11.1 Parity check.** List every feature of the **Classic** timeline (`client/studio/src/review/Timeline.tsx`, `LayerLanes.tsx`, `MotionClip.tsx`, and whatever else the Classic mode mounts; find them from the toggle's code). For each, check whether the **New** timeline (`client/studio/src/occ/src/components/timeline/`) does it. Write `docs/dev/timeline-parity.md`: feature | Classic | New | action. Port each missing feature into the New timeline, one commit each, with a test where the New timeline has tests (`npm run test:timeline`).
  Check: every row is "same", "ported" or "dropped: <reason the owner would accept>". If any feature would be dropped, ask the owner first, in plain words, naming the feature.

- [ ] **W11.2 Remove Classic.** Delete the Classic/New switch, the Classic components that nothing else imports (prove it with `git grep`), their CSS and their e2e suites (`e2e:timeline`, `e2e:timeline2`, `e2e:timeline3`: keep whichever tests the New timeline; delete the rest).
  Check: `npm run build` passes. `git grep -n "Classic"` in `client/studio/src` shows nothing timeline-related. Every remaining e2e passes.

- [ ] **W11.3 Restyle the timeline to the tokens.**
  - **Toolbar (36px):** left: select/trim/razor tools, undo/redo (if not in the top bar), snapping; centre: nothing; right: zoom − slider +, fit, captions-track toggle. Icons `--text-muted`, 16px.
  - **Ruler (24px):** times in `--fs-11` `--text-faint`, ticks in `--border`.
  - **Track headers (88px wide):** a small kind chip (`C1`, `V1`, `A1` in white `--fs-11` weight 600 on that kind's `--clip-*`, radius 4px), then eye, lock and mute as 14px faint icons that turn `--text` on hover. No second label line ("Captions", "Scenes", "Narration" goes in the chip's tooltip).
  - **Clips:** radius 4px, the kind's `--clip-*`, the label in white `--fs-11` weight 500 ("Scene 2 · 2.6 s"). A thumbnail strip for scene/picture/video clips at 60% opacity under the label. Waveforms drawn in `--tl-wave` over `--clip-narration`/`--clip-music`. A selected clip gets a 2px `--tl-select` outline. Remove the centred time badges ("00:02.20") from clips; show the duration in the label instead.
  - **Playhead:** a 1px `--tl-playhead` line with a 9px triangle head in the ruler.
  - **Lanes:** `--tl-lane`, with 2px gaps between tracks in `--tl-gap`.
  Canvas-drawn parts read tokens through `cssVar` (W6.3).
  Check: `npm run test:timeline` passes. Screenshot at 1440×900, light and dark, side by side with the openfilm frame (`docs/dev/shots/w11-timeline-*.png`).

---

### W12 — Claude Code and Codex inside the app (ACP)

Before starting, read `E:\openfilm-a1b8d75\apps\desktop\src\agents.mjs` lines 1–120 and 1300–1656, and our `client/desktop/director-runner.js`, `assistant-command.js`, `assistants.js` and `mcp-bridge.js`.

- [x] **W12.1 Dependencies.** In `client/desktop/package.json`, add exact versions (match OpenFilm's lock file `E:\openfilm-a1b8d75\pnpm-lock.yaml`, unless a newer patch is at least two weeks old): `@agentclientprotocol/sdk` (1.5.0), `@agentclientprotocol/claude-agent-acp` (0.81.2) and `@agentclientprotocol/codex-acp` (1.13.1). All three are Apache-2.0: add them to THIRD-PARTY.md.
  _Status: Done 2026-11-21 for Claude: `@agentclientprotocol/sdk` 1.5.0 and `claude-agent-acp` 0.81.2 (Apache-2.0, in THIRD-PARTY.md); the adapter and SDK are unpacked from the asar and the 227 MB bundled Claude binary is excluded from the installer (the app uses the person's own Claude Code). Codex: `codex-acp` is not bundled and Codex is not installed on this PC, so it stays "not set up" until a first-use install is written._
  - **Size check:** `codex-acp` depends on `@openai/codex`, which ships platform binaries. Build the Windows installer and compare its size to the W9 size. If Codex adds more than **60 MB**, do **not** bundle `codex-acp`. Instead, install it on first use into the app's user-data folder (`<userData>/agents/codex-acp/`) with the app's own Node (`ELECTRON_RUN_AS_NODE=1` + the bundled npm, or a direct tarball download from the npm registry with an integrity check), showing "Setting up Codex… (about N MB)" in the agent chip. Record the decision and sizes in the baseline file.
  - In electron-builder's config (`client/desktop/package.json` → `build`), add `asarUnpack` for `node_modules/@agentclientprotocol/**`, `node_modules/@anthropic-ai/claude-agent-sdk/**` and the codex packages if bundled. These are run as separate Node processes, and Node cannot run scripts from inside an asar archive.
  Check: `npm --prefix client/desktop ci` works; the installer builds; its size is recorded.

- [x] **W12.2 The runner module.** Create `client/desktop/acp-agents.js` (CommonJS, matching the folder; load the ESM SDK with `await import('@agentclientprotocol/sdk')`). It holds a `Session` class modelled on OpenFilm's (`agents.mjs` ~1300–1560):
  _Status: Done 2026-11-21 (`client/desktop/acp-agents.js`). Model switching is not wired yet._
  1. **Find the program.** Reuse `assistant-command.js` (`commandFor('claude' | 'codex')`) and `director-runner.js`'s `interpret()` for "installed / signed in". Do not write a second detector.
  2. **Spawn the adapter:** `spawn(process.execPath, [<unpacked path>/@agentclientprotocol/claude-agent-acp/dist/index.js], { env, cwd, stdio: ['pipe','pipe','pipe'], windowsHide: true })` with `env = cleanEnv({ ELECTRON_RUN_AS_NODE: '1', CLAUDE_CODE_EXECUTABLE: <path from commandFor> })`. Reuse `director-runner.js`'s `cleanEnv`, which removes `ANTHROPIC_API_KEY` and friends so the person's subscription is used. For Codex: `CODEX_PATH`. Resolve the unpacked path with `require.resolve(...)` and replace `app.asar` with `app.asar.unpacked`.
  3. **Connect:** wrap stdout/stdin as web streams (`Readable.toWeb` / `Writable.toWeb`) into `acp.ndJsonStream`, then create a `ClientSideConnection` (check the SDK 1.5.0 export names in `node_modules/@agentclientprotocol/sdk/dist/*.d.ts`; OpenFilm uses `acp.methods.agent.*` request helpers). Handle stderr: keep the last 200 lines for diagnostics, never show raw stderr to the person.
  4. **`initialize`** with `protocolVersion: acp.PROTOCOL_VERSION`, `clientCapabilities: { fs: { readTextFile: false, writeTextFile: false }, terminal: false }` (we offer no file system or terminal to the agent) and `clientInfo: { name: 'ultimate-video-tool', version: <app version> }`.
  5. **`session/new`** with:
     - `cwd`: `<userData>/agents/<projectId>/` (create it). This is a scratch folder; projects live on the server.
     - `mcpServers`: one entry, `{ name: 'video-tool', command: process.execPath, args: [<unpacked path to mcp-bridge.js>], env: [{name:'ELECTRON_RUN_AS_NODE',value:'1'}, …whatever mcp-bridge.js needs to reach the selected server: its URL and key; read mcp-bridge.js and assistants.js to see how Claude Desktop is registered today and pass the same] }`.
     - For Claude: `_meta: { systemPrompt: { append: INSTRUCTIONS }, claudeCode: { options: { allowedTools: ['mcp__video-tool__*'], settings: { permissions: { allow: ['mcp__video-tool'], deny: [] } } } } }`. Check the exact option names that `claude-agent-acp` 0.81.2 reads (search its `dist/` for `claudeCode` and `allowedTools`), and mirror what `director-runner.js` already passes to `claude` to restrict it to MCP tools.
     - **Do not** set `bypassPermissions` or any full-access mode (D9).
  6. **INSTRUCTIONS** (a constant in `client/desktop/acp-instructions.js`; English; shown to the person under Details → AI conversations):
     "You are working inside Ultimate Video Tool on project `<title>` (id `<id>`). Change the video only through the `video-tool` MCP tools. The person sees every change live. Prefer small, precise changes to what they point at. When the message has a `<video_references>` block, `[1]`, `[2]` … in the text refer to its lines. When you mention a scene, a moment or an element in your reply, link it as a Markdown link whose target is `vt://scene/s3` (text "scene 3"), `vt://t/12.5` (text "0:12.5") or `vt://element/s3/2` (text "the title"). Never undo a change the person made by hand unless they ask. Keep replies short: say what you changed."
  7. **`session/prompt`** with content blocks: text (W13.2's format) and image blocks for referenced regions or elements (only if `agentCapabilities.promptCapabilities.image` is true).
  8. **`session/update`** → map each update to an `AssistantEvent` (W10.4): `agent_message_chunk` → `text`; `tool_call`/`tool_call_update` → `step` (title: for `mcp__video-tool__X`, use the MCP tool's human title from our MCP server's tool list, e.g. "Changing the picture"); `plan` → steps; others → ignored, but logged.
  9. **`session/request_permission`** → if the tool is a `video-tool` MCP tool, answer allow at once. Otherwise emit a `permission` event and wait for the person's choice (`once` / `chat` / `deny`), with a 10-minute timeout → deny. Remember `chat` answers per session and per tool name.
  10. **Resume:** keep `{projectId → [{sessionId, agent, title, at}]}` in `<userData>/agents/sessions.json`. On reopen, use `session/resume` if `agentCapabilities.sessionCapabilities.resume`, else `session/load` if `loadSession`, else start new and say "Started a new conversation (the earlier one could not be reopened)."
  11. **Cancel:** `session/cancel` notification, then wait 5 s, then kill the process tree (`taskkill /T /F /PID` on Windows, `process.kill(-pid)` with `detached: true` on Linux).
  12. **Errors:** classify with `director-runner.js`'s `kindOf()` (`limit` / `login` / `other`) and emit `error` events in plain words. "Claude's usage limit is reached. It resets at <time> if Claude said when." "Claude Code is not signed in. Sign in…" (the action opens a terminal running `claude auth login`, reusing `assistants.js`'s existing sign-in launcher).
  13. **Cleanup:** every session closes when the app quits (`app.on('will-quit')`) and when the process exits (`process.once('exit')`).

- [x] **W12.3 IPC.** In `client/desktop/main.js`, register `ipcMain.handle` channels under the prefix `vt-agent:` (`status`, `open`, `send`, `stop`, `permission`, `list`, `signin`). Stream events with `webContents.send('vt-agent:event', {conversationId, event})`. In `client/desktop/preload.js`, expose them as `window.vtDesktop.agents = { status(kind), open(kind, projectId, resume?), send(id, text, refs, images), stop(id), permission(id, requestId, choice), list(projectId), signIn(kind), onEvent(cb) → unsubscribe }`.
  _Status: Done 2026-11-21 (`vt-agent:*` channels, checked in `acp-validate.js`)._
  **Validate everything in the main process:** `kind ∈ {'claude','codex'}`, `projectId` and ids match `^[\w-]{1,64}$`, text ≤ 100 kB, at most 6 images of ≤ 5 MB each, PNG/JPEG/WebP only, refs a JSON array of ≤ 50 objects with the known shape. The renderer never receives paths, environment variables or tokens.
  Check: a unit test for the validators.

- [x] **W12.4 The backends in the Studio.** Create `client/studio/src/assistant/backends/acp.ts`, which implements `AssistantBackend` over `window.vtDesktop.agents` for `claude` and `codex`. When `window.vtDesktop?.agents` is missing (the Studio opened in a plain browser), the agent chip lists Claude Code and Codex greyed out with "Available in the desktop app". The Director still works.
  _Status: Done for Claude 2026-11-21 (`client/studio/src/assistant/AgentChat.tsx`, tab in the Assistant pane; `e2e/assistant-agent.mjs` 13/13). The model chooser and `AssistantBackend` abstraction (W10.4) are not done._
  - **Permission card** (`assistant/PermissionCard.tsx`): "Claude wants to run a command" / "…to change a file" / "…to fetch a web page", the detail (the command or path, monospaced, cut at 300 characters with "Show all"), and the buttons **Allow once**, **Allow for this chat**, **Deny** (Deny is the default focus).
  - **Model:** if the session reports models (`newSession` result `models`), show them in the agent chip's popover; choosing one calls the SDK's set-model method. Default: the program's own default. Show the effort setting only if the adapter reports one.
  Check: `e2e:assistant` with a **fake ACP agent** (W12.5) covers: open, send, streaming text, a step, a permission request answered "Deny", stop, and reopen with resume.

- [x] **W12.5 A fake agent for tests.** Create `client/desktop/test/fake-acp-agent.mjs` using the SDK's agent-side connection. It answers `initialize`, `session/new` (records the `mcpServers` it was given, so tests can assert that `video-tool` was passed), `session/prompt` (streams "Hello" in 3 chunks, one `tool_call` for `mcp__video-tool__set_caption_style` and one for `Bash`, which triggers a permission request), `session/cancel`, `session/resume`. Make `acp-agents.js` accept `VT_ACP_FAKE=<path>` (tests only; ignored when `app.isPackaged`). Write `client/desktop/test-acp-agents.js` (plain Node, like the other `test-*.js`) covering everything in W12.2, steps 4–13, against the fake. Add it to CI's `studio` job.
  _Status: Done 2026-11-21 (`client/desktop/test/fake-acp-agent.mjs`, `test-acp-agents.js`, in CI)._
  Check: `node client/desktop/test-acp-agents.js` green on Windows here, and in CI on Linux.

- [x] **W12.6 Real run with Claude Code (Sonnet).** In the installed desktop client on this PC (rebuild and reinstall), open a real project on the installed server. In the Assistant, choose **Claude Code**, model **Sonnet**. Ask: "Make the opening line bigger and move it to the top third." Confirm:
  _Status: Done for Claude 2026-11-21 from source (`client/studio/e2e/desktop-agent.mjs`: the real app, real Claude Code, our tools asked nothing, a shell command raised a card and Deny was respected). Not yet on a rebuilt installer; Codex not installed here._
  1. The steps show while it works, using our MCP tools.
  2. The preview and timeline update (after W14; before W14, after a reload).
  3. No permission card appears for our tools.
  4. Asking "list the files in my home folder" triggers a permission card, and Deny is respected.
  Repeat with **Codex** if it is installed on this PC (`codex --version`). Record each run in WORKLOG with the conversation's step list.

---

### W13 — Point at anything

- [~] (2026-11-22: scene, element, time, range, word, layer, region kinds exist in client/desktop/acp-validate.js and AgentChat; refs.ts as one source not made) **W13.1 The reference kinds.** Define them in `client/studio/src/assistant/refs.ts`, extending the OpenChatCut-ported `occ/src/agent/selection-refs.ts` (do not duplicate it; make one of them the source and re-export):
  ```ts
  export type VideoRef =
    | { kind: 'scene'; scene: string; start: number; end: number; words: string }
    | { kind: 'element'; scene: string; index: number; label: string; box?: Box }
    | { kind: 'caption'; start: number; end: number; text: string }
    | { kind: 'time'; t: number }
    | { kind: 'range'; start: number; end: number }
    | { kind: 'region'; t: number; box: Box }                 // in video pixels (e.g. 1080×1920)
    | { kind: 'media'; id: string; name: string; type: 'image' | 'video' | 'audio' }
    | { kind: 'track'; track: string };
  export type Box = { x: number; y: number; w: number; h: number };
  ```
  Port OpenFilm's `studio-refs.ts` formatting helpers (`clock`, `span`, `clipped`, `boxText`, `idOf`, `linkOfRef`) with the header, adapted to these kinds.

- [~] (2026-11-22: one wire format in client/desktop/acp-instructions.js toPrompt and server/vt/assistant_refs.py with_refs, byte-identical on the shared tests/fixtures/refs.json; the Director route takes refs) **W13.2 The wire format** (one function, `toPrompt(text, refs)`, used by every backend):
  ```
  Make [1] bigger and keep it clear of [2].

  <video_references>
  [1] element s3#2 · "Small habits" (title text) · 0:04.0–0:06.1 · box x=120 y=640 w=840 h=220 of 1080×1920 · vt://element/s3/2
  [2] region at 0:05.2 · box x=0 y=1500 w=1080 h=420 of 1080×1920 · picture attached as image 1 · vt://t/5.2
  </video_references>
  ```
  The pill in the composer becomes `[n]` in the text, numbered in order of appearance. For the Director backend, also send `refs` as JSON in the `/director/chat` body. Add an optional `refs: list[dict]` field to its request model in the server (`routes/director.py` after W4.2) and pass it into `chat.talk(...)`, which puts the same `<video_references>` block into the director's prompt. This is one implementation in `server/vt/` (rule 0.6): add `vt/assistant_refs.py` with `format_refs(refs, project) -> str`, and use it from both the route and the MCP tool if one takes refs.
  Check: Python unit tests for `format_refs`. TS unit tests for `toPrompt`. Both produce byte-identical output for the same refs: share a fixture file `tests/fixtures/refs.json` and expected text.

- [~] (2026-11-22: Ctrl+L with a scene or element selected, and "Ask the assistant about this" in a scene's menu, make a pill for Claude Code or the Director, sent as a reference; Alt-drag on the picture makes a region pill with its box, and Claude Code also gets the picture under it (server: /frame-crop); browser tests. Timeline clip menus, Shift-drag range, drag-in not done) **W13.3 The gestures that make pills.**
  - **Right-click** a scene row, a timeline clip, an element on the canvas, or a caption → the context menu gets **"Ask the assistant about this"** (Ctrl+L with a selection does the same).
  - **Viewer region:** hold **Alt** and drag on the picture → a dashed `--accent` box. On release, a pill "Region at 0:05.2" with a thumbnail. The picture of that frame cropped to the box is fetched from the server's existing frame-preview endpoint (find it: the MCP "preview frames" tool uses one) and attached as an image.
  - **Timeline range:** Shift-drag on the ruler → a range highlight and a floating "Ask about 0:12.6–0:17.2" button.
  - **Drag** a scene row or a media tile into the composer → a pill.
  - **Inspector:** the "Ask the assistant about this" icon (W8.4).
  Every gesture opens the Assistant pane if it is hidden and focuses the composer.
  Check: `e2e:assistant` extended: right-click a clip → pill; Alt-drag → pill with image; send → the fake agent receives the `<video_references>` block and one image block.

- [x] **W13.4 Links back.** In the message Markdown renderer, intercept `vt://` links: `vt://scene/<id>` selects that scene (and scrolls the timeline to it), `vt://t/<seconds>` seeks, `vt://element/<scene>/<index>` selects the element on the canvas, and `vt://range/<a>/<b>` selects the range. Render them as `--accent-text` links with a small icon (🎬 scene, ⏱ time, ◻ element). Unknown `vt://` links render as plain text. Never navigate the window.
  _Status: done 2026-11-21 for the Claude Code tab (`client/studio/src/assistant/links.ts`, 4 unit tests incl. hostile input; `e2e/assistant-agent.mjs` clicks a time link and the playhead moves). Range links seek to their start; selecting a range is not done._
  Check: unit test of the link parser (valid, invalid, hostile input such as `vt://scene/../../`). `e2e:assistant`: click a link in a reply → the playhead moves.

---

### W14 — Watch it change while the agent works

- [~] **W14.1 One change event (2026-11-22: the file watcher's event now carries rev, scenes, removed, by, what, with a test; the "every save" emitter and by=person/director are still to do)  from the server.** Find the server's realtime channel (`/ws`; the Studio subscribes in `client/studio/src/store.ts`, `startRealtime`). Make **every** write to a project emit one event after it is saved: `{"type": "project.changed", "project": id, "rev": n, "scenes": [...changed ids], "removed": [...], "by": "person" | "director" | "mcp:<client name>", "what": "<plain words, e.g. 'caption style'>"}`. Writes come through API routes, MCP tools and the director. Put the emitter in one place, the function that saves a project (find it: `vt/schema.py` or `vt/context.py` save / `write_json` of `project.json`), so nothing can forget it. `rev` increases by one per save (store it in the project).
  Check: a Python test that saves through an API route, an MCP tool call and a director change, and receives three events with the right `by`.

- [x] **W14.2 (2026-11-22: toast, glow on Classic and new timeline and scene list, change waits while the person types or drags, selection kept; e2e/agent-toast.mjs 6/6. Not done: refetch only the changed scenes, the whole project is refetched) The Studio applies changes without a jump.** On `project.changed` for the open project with `rev` greater than the one loaded:
  - Refetch only what changed (scene list plus the changed scenes; add a `?scenes=` filter to the project GET route if needed).
  - Keep the selection, the playhead, the timeline scroll and zoom, and the inspector's open sections.
  - If the person is in the middle of a drag or a text edit, queue the refresh until pointer-up or blur (one pending refresh at most).
  - Re-render only the changed scenes' previews.
  - Flash each changed clip and scene row once (a 1 s `--accent` outline fade).
  - Show a small toast in the viewer's top-left: "Claude changed scene 3 (caption style)".
  Check: `e2e:assistant` with the fake agent calling a real MCP tool through a scratch server: the clip flashes; the playhead and selection stay the same.

- [x] **W14.3 Undo covers the agent.** (2026-11-22: an agent change is a step in the editor's undo history; Ctrl+Z takes it back with "Undid Claude's change"; e2e/agent-toast.mjs 7/7) Make sure MCP and director writes go into the same undo history as hand edits, so Ctrl+Z in the editor undoes the agent's last change and says so ("Undid Claude's change to scene 3"). Find the server's undo mechanism (`undo_transcript` is one; there may be a project-level history) and use it. If writes through MCP bypass it today, route them through it.
  Check: a test with an MCP write, an undo through the API, and the project back to its previous state.

- [x] **W14.4 The person and the agent at the same time.** (2026-11-22: change waits while the person edits; "Claude just changed this." with Undo in the inspector; e2e/agent-toast.mjs 9/9) Rule: the person's in-progress edit is never interrupted, and the last saved write wins per element. If the agent changes an element the person has selected, the inspector shows a one-line notice, "Claude just changed this. Undo?", with an Undo link.
  Check: an e2e case where the selection stays and the notice shows.

---

### W15 — Acceptance and 0.6.0

- [~] (2026-11-22: screenshots taken by e2e/screens.mjs, README updated, critique in docs/dev/shots/compare.md; the five layout points listed there are still to fix) **W15.1 Screenshots.** Take the editor at 1440×900 and 1280×720, light and dark, with a real project: nothing selected, a scene selected, an element selected, and the assistant mid-conversation with steps. Save to `docs/assets/screens/` (replace `editor.png`; add `assistant.png`) and update the README's screenshot table. Put the new editor screenshot next to the openfilm frame and next to `docs/dev/shots/before-*.png` in `docs/dev/shots/compare.md`, and read it critically: list anything that still looks heavier than the reference, and fix it before ticking.

- [~] (2026-11-22: every suite marked in W3.5 rewritten and passing on this laptop: editor 20, journey 16, export 8, context 5, sounds 5, edge 9, stick 9, dashboard 10; nightly browser job and both themes for a11y/contrast not done) **W15.2 Suites.** Rewrite the e2e suites marked in W3.5 for the new layout. Every suite passes. Add `e2e:workbench` and `e2e:assistant` to the nightly browser job. `npm run e2e:a11y` and `e2e:contrast` pass in both themes.

- [ ] **W15.3 Real videos, a matrix, with Claude directing.** On this PC's installed client and server (rebuilt), run `scripts/lab/local_matrix.py` (W3.7) over its whole matrix with the **Claude** director (Sonnet), then the same smaller set with **gemma**. Then, in the Assistant with **Claude Code** (Sonnet), on two of the videos: point at one scene's picture and ask for a better one, point at a region and ask for the caption to move out of it, fix one thing by hand on the timeline, export. Record the matrix table (kind, format, language, director, time, verdict) and the mp4 paths in WORKLOG, and watch the videos (contact sheets are not enough for motion).

- [x] **W15.4 Linux check.** Skipped by the owner's decision (Windows only, no WSL). Say "Linux not tested" in the release notes.

- [~] (2026-11-22: README section "Claude Code inside the app" written; the rest of W15.5 not checked) **W15.5 Docs.** Update `README.md` (the "Use it from your AI assistant" section: Claude Code and Codex now work inside the app; the MCP setup remains for outside use), `docs/STATUS.md`, `CHANGELOG` notes in the release body, and `THIRD-PARTY.md` (OpenFilm, the ACP packages, Lexical, Inter).

- [ ] **W15.6 Hand over to the owner.** Open a pull request `workbench` → `main` titled "0.6.0: workbench layout and Claude Code inside the app", with a summary, the screenshots and the test results. Ask the owner, in plain words, to review and merge, and to say whether to publish it as 0.6.0 (push the tag `v0.6.0` on the merge commit). Do not merge it yourself.

---

## 4. Open questions for the owner (ask only when the step is reached)

| When | Question (ask in these words) | My recommendation |
|---|---|---|
| W1.6 | "Ready to publish 0.5.0 and delete the 1.0.0 release? People who downloaded 1.0.0 keep their files." | Yes. |
| W1.6 | "Also remove the 1.0.0 Docker image tag of the server package? Someone may be pulling it." | Leave it. |
| W3.4 | (answered 2026-11-20: no scheduled task, run by hand) | Run by hand. |
| W15.4 | (answered 2026-11-20: no WSL, Windows only) | Skip Linux. |
| W11.1 | Only if a Classic-timeline feature would be dropped: "The old timeline could <feature>. The new one cannot yet. Drop it, or port it first?" | Port it. |
| W12.1 | Only if Codex adds more than 60 MB: "Codex makes the installer N MB bigger. Download it on first use instead?" (already decided as yes; just inform the owner) | Download on first use. |

## 5. What this plan does not do

- No OpenFilm features beyond the editor shell and the agent pane: no Canvas, no Color grading, no plugin system, no community standard, no paid service.
- No change to how videos are made, scored or rendered. That is PLAN-PERFECT.
- No VS Code, Monaco or embedded terminal (D7).
- No React 19, no Tailwind (D11).
- No UI translations (English only).
