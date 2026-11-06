# M1: how the director link behaves today (before the helper)

Seen on 2026-11-05 between 21:47 and 21:52, against the real server (`http://192.168.123.47:8790`) with the installed desktop app (`Ultimate Video Tool.exe`, started with `ELECTRON_RUN_AS_NODE` removed).

## Claude disappears with the window
| Moment | `GET /api/directors` lists |
|---|---|
| Server restarted at 21:33, app not running | Best available, Local AI, Claude on the server (not logged in). **No Claude or Codex on this PC.** Nothing came back by itself in the 14 minutes after the restart. |
| App started 21:47:16, window open | the same, plus **Claude on MSI-LAPTOP (ready)** and **Codex on MSI-LAPTOP (not ready)** |
| App window closed 21:50 (`CloseMainWindow`, the app exited within 8 s) | Claude and Codex on MSI-LAPTOP are **gone** again |

- `desktop.log` from earlier today shows the companion retrying `connect ECONNREFUSED 192.168.123.47:8790` every 4 s for as long as the app is open and the server is down, and nothing at all once the app is closed.
- The code agrees: `ClientCompanion` is created in the app's main process (`main.js`, `app.whenReady`), is closed in `before-quit`, holds one `/ws` link (`select`), and handles one task type, `direct`. A second `direct` while one runs is refused at once: "This computer is already directing a video."
- Wording bug seen: Codex on MSI-LAPTOP is not ready, and the note under it says "Open Claude Code and log in on this device." (`directors.listing`, one text for both assistants).

## The other AI steps of such a video get no AI
No video on this server was ever directed from a computer (0 of the projects have `director.who` starting with `claude@` or `codex@`), so this is shown with the real provider code instead:

```
provider for a video directed by claude@b8ea10c0: NoProvider | available(): False
ai_enabled() inside that video: False
complete_json -> AIUnavailable: claude@b8ea10c0 directs this video; no other AI is asked.
```

`Pipeline._director_provider` returns this `NoProvider` for every `claude@...` and `codex@...` director. So understanding the video (`stage_context`), the delivery notes (`voice_direction`), the picture checks (`vision`), the last look in `stage_compose` (it returns at once for `NoProvider`) and the title all get no AI. Only the planning session runs, through MCP.

## Also seen
- The tool rows in AI conversations are written with the name `assistant` for every `/mcp` client (the environment variable `VT_MCP_CLIENT` is not set per connection on the server), and the broker's own rows use `claude on <device id>`. So a video directed from a PC would show three different names for one director.
