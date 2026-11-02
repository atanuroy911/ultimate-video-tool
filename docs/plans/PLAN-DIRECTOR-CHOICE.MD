# Who directs: the person picks, and Claude on their own PC can direct a server elsewhere

Status: **plan**, 2026-11-01. The owner asked:
- the UI chooses who directs when more than one can;
- Claude installed on the client PC directs, making its calls to the server.

## The directors

| Director | Runs where | How it is reached | Today |
|---|---|---|---|
| Local AI | the server (Ollama) | `llm.chat_json` | works; weaker. On the billionaire script: 13 of 50 shots named the characters, some pictures carried words |
| Claude on the server | the server, the person's Claude login there | `ClaudeCLIProvider` (`claude -p`) | works when Claude Code is installed and logged in on the server |
| **Claude on this PC** | the client PC | the client starts `claude -p` locally; Claude calls the server's MCP | **new** (this plan) |
| Claude by hand | any Claude Code or Desktop session connected by MCP | the "waiting for Claude" queue (`list_pending_requests` → `get_planning_task` → `submit_scenes`, plan.edit) | works; needs the person to ask Claude |
| Cloud | the server, through OpenRouter | PLAN-CLOUD-AI | planned |

## Claude on this PC directing a server elsewhere

The server cannot start a program on the client, so the client does the starting. The connection already exists:
- Pairing gives the client a device token.
- The desktop app registers Video Tool with the local Claude through `desktop/mcp-bridge.js`, which reaches the server's `/mcp` with that token.

What is new is the server asking for a director.

1. **The client says what it can do.** On connecting, the desktop app looks for `claude` (`claude --version`, `claude auth status`) and tells the server over `/ws`, with its device token: `{"director": "claude", "version": ..., "logged_in": true}`. The server keeps a list of directors per connected device. It forgets one when the socket closes.
2. **The server asks.** When a project reaches its plan stage and its director is "Claude on <device>", the server:
   - puts a director request in that device's queue;
   - sends it over `/ws`: `{"type": "direct", "project": id, "task": "plan"}`;
   - shows "Waiting for Claude on <device>" in Progress.
3. **The client runs Claude headless.** It runs `claude -p "<the director task>" --mcp-config <bridge to the server's /mcp> --allowedTools "mcp__video-tool__*" --output-format stream-json`:
   - It only gets Video Tool's tools: no shell, no files.
   - The task is the same text `get_planning_task` gives today, plus the craft rules for the plan (picture.place, picture.drawable, the script rules).
   - Claude reads the plan, edits it with plan.edit (set_cast, set_place, set_prompt, set_moment_place, merge, set_medium), checks `craft_check`, and approves.
   - Every call is a normal MCP call to the server, logged with its `why` like any director call.
4. **Progress comes back.** The client streams Claude's progress lines to the server (`/ws`, `{"type": "director_log"}`), and Progress shows them live. When Claude approves, the pipeline continues on the server (pictures on the server's GPU, render).
5. **When the PC is not there** (closed, asleep, Claude logged out): after a timeout chosen in Settings (default 2 minutes, or "wait for me"), the server falls back to the next director in the person's order, usually the local AI, and says so on the project. A video never waits forever unless the person asked it to.
6. **Browser-only clients** cannot start programs. They do not offer "Claude on this PC". They can still use "Claude by hand": the Studio shows the one line to paste into Claude Code ("Direct the waiting Video Tool video").

**Security:**
- Claude's tools are limited to Video Tool's MCP.
- The bridge uses the device's own token, which is revoked with the device.
- The server never receives the person's Claude credentials.
- Claude's usage stays on their own account.
- The server records which device directed each project.

## The choice in the UI

- **New page → "Who directs this video?":**
  - **Best available** (default): the order from Settings.
  - **Local AI:** fastest, free, weaker.
  - **Claude on this PC.**
  - **Claude on the server.**
  - **Cloud**, once configured.

  Only the ones that can run right now are enabled, each with a one-line reason ("Claude is not logged in on this PC: open Claude Code once").
- **Settings → AI → "Directors":** the fallback order, the wait time for an absent PC, and Claude usage today (from `claude_usage.json`).
- **The project** records `director: {"who": "claude@roy-pc", "at": ...}` and shows it on Review. Comparing two directors on the same script is "Make again with another director": a copy of the project, as the lab does (`scripts/lab/director_run.py`, `claude_direct_billionaire.py`).

## Steps

1. Director registry on the server: what can direct now (local AI, Claude on the server, connected devices' Claude). `GET /api/directors`.
2. Project and New-page choice, the fallback order, and the per-project record.
3. Desktop app: detect Claude, announce it over `/ws`, run the headless director on a request, stream its log; the timeout fallback.
4. The director task text: the planning task plus the plan rules, one function for the MCP prompt and the headless run.
5. Tests:
   - a fake device that answers `direct` requests;
   - a timeout falling back to the local AI;
   - the tool allowlist (a director run cannot call anything but Video Tool tools).
6. Lab: the same script directed by each director, judged side by side (the billionaire video is the first pair).
