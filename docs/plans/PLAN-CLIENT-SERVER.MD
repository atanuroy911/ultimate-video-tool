# Plan: a thin client and one server that holds the brain

> **2026-11-05: pairing was removed** (owner: "remove the key pairing altogether... just let user put the ip address"; [PLAN-PERFECT.MD](PLAN-PERFECT.MD) decision 7, step M5b).
> Wherever this plan says pairing code, `/api/pair`, paired devices, per-device tokens, revoke or "New pairing code", read this instead: a computer on the server's own network
> (this computer, a private or link-local address, Tailscale) connects with the address alone. A request from anywhere else, or one a proxy or tunnel forwarded, still needs the
> server's own key (`Authorization: Bearer`, the `vt_token` cookie or `?token=`), and a request from a web page (another site's `Origin`, or a `Host` that is not an address or a
> local name) is refused. `server/vt/server/serve.py` is the one place that decides (`trusted`). A computer names itself with the `X-VT-Device` header. `clients.py` is gone.
> The separate "share this computer's engines" feature (`vt engine run`, `/v1/pair`) keeps its own code.

Owner's request (2026-10-31): organise the project in two halves. The **server** runs anywhere that holds the models (Ollama, ComfyUI, the voices);
the **client** is only the interface. Both are installable and runnable. The client finds a server on the local network, or the person types its
address; both can also be installed on the same computer and simply work together.

**What changes from [PLAN-PACKAGING.MD](PLAN-PACKAGING.MD).** That plan (2026-10-28) already ships two products, but splits them in a different place:
the app carries the Studio *and the whole pipeline* (Python, PyTorch, Node, FFmpeg), and the Engine only serves models. Here the pipeline moves to the
server. The client keeps nothing but the window.

## 1. Why this split (decided, with the trade-offs)

| For | Against, and the answer |
|---|---|
| The client installs in seconds: no Python, no PyTorch, no 10-20 minute first start, no GPU needed. Laptops, a second PC, a phone (PWA) all work. | **Files travel**: recordings and uploads go to the server, finished MP4s come back. On a LAN this is seconds; over the internet it is slow. Uploads are resumable and previews stream. |
| The heavy work (transcription, voices, rendering, pictures) runs next to the GPU and the models, with no second hop. | **One server, several people**: projects and GPU queues are shared. The GPU locks exist (`gpu.voicestudio`, `gpu.comfy`); per-person projects are not in scope for v1. |
| The client loads the Studio **from the server**, so the window and the server can never be different versions (the "405: the server is older than this page" class of bug ends). | **Offline client**: with the server unreachable, the client shows the connection screen, nothing else. Same-computer installs never hit this. |
| One server concept instead of two: today's Studio backend (`vt studio`) and Engine hub (`vt engine run`) both pair, both serve HTTP, both start services. | **Auth on every route**: the Studio API was loopback-only and has no auth. Every route now needs the pairing token (the Engine gateway's pairing is reused). |

The engine registry stays: the server may still use a ComfyUI, an Ollama or a VoiceStudio on a third computer (the owner's V100 and RTX 3060 today).

## 2. The two halves

```
 CLIENT (Electron shell, or the PWA in a browser)           SERVER (vt server)
 ┌───────────────────────────────┐                        ┌─────────────────────────────────────────────────────────┐
 │ connection screen             │  mDNS _videotool._tcp  │ /.well-known/video-tool  (name, version, needs pairing)  │
 │   found on this network: ...  │ ◄────────────────────► │ /api/pair                (code -> token)                 │
 │   or type an address          │                        │ /api/*  /ws              (token on every request)        │
 │ pair once (6-digit code)      │  HTTP + WS + token     │ the Studio UI (client/studio/dist), served by the server        │
 │ then: the Studio, loaded      │ ─────────────────────► │ projects, pipeline, render (Node, FFmpeg, Chrome)        │
 │   from the server             │                        │ MCP over HTTP (vt-mcp --http, same token)                │
 │ remembers servers + tokens    │                        │ engines: Ollama, ComfyUI, VoiceStudio (here or remote)   │
 └───────────────────────────────┘                        └─────────────────────────────────────────────────────────┘
```

| | Client | Server |
|---|---|---|
| Contains | `client/desktop/` (Electron shell: connection screen, saved servers, OS keychain for tokens, menus) and the PWA manifest | `server/vt/`, `server/renderer/`, `server/assets/`, `server/design/`, `client/studio/dist` (served), the engine installers |
| Needs | nothing (Electron bundles its runtime) | Python 3.11 + locked packages, Node 20, FFmpeg; a GPU is optional |
| Installs as | `.exe` / `.dmg` / `.AppImage`, about 100 MB | the setup wizard or the Engine package (zip, Docker image), as in PLAN-PACKAGING |
| Runs as | a window | a service (`vt server service --install`), or started by the client on the same computer |

**Same computer.** The client looks at `127.0.0.1:8765` first. If a server is installed there but not running, it starts it (as `client/desktop/main.js` does
today). Loopback needs no pairing.

**Discovery.** The server announces `_videotool._tcp.local` with its name, version and port (the `zeroconf` package). The client lists what it hears and also
sends one UDP broadcast on port 8767 as a fallback for networks that block multicast. Typing an address always works.

**Claude and other assistants.** Claude Code runs on the client computer. `.mcp.json` points at the server's HTTP MCP (`vt-mcp --http`, which already
exists) with the token, instead of starting a local Python. On the server computer the stdio form keeps working.

## 3. The repository

| Folder | Half | Note |
|---|---|---|
| `client/desktop/` | client | becomes the connection-first shell |
| `client/studio/` | client source, server-served | built into `client/studio/dist`, which the server serves; the client never bundles its own copy |
| `server/vt/`, `server/renderer/`, `server/assets/`, `server/design/`, `server/packaging/engine/` | server | |
| `scripts/`, `tests/`, `docs/` | both | |

The boundary comes first (two entry points, two installers, auth); moving folders into `client/` and `server/` is a separate, mechanical commit afterwards,
because `pyproject.toml`, the tests and `scripts/check_docs.py` name today's paths.

## 4. Phases

| Phase | What | Done when | Verify |
|---|---|---|---|
| **CS1 One server** | `vt server` = `vt studio` + the Engine hub in one process: one port, one pairing, one service. `vt studio` and `vt engine run` stay as aliases | the Studio and a paired engine client both work against one `vt server` | `tests/test_server_merge.py`; the existing API and hub tests pass unchanged |
| **CS2 Auth** | token on every `/api` and `/ws` route except `/.well-known`, `/api/pair` and static files; loopback is exempt | a request from another address without a token gets 401; with it, 200 | `tests/test_server_auth.py` |
| **CS3 Discovery** | mDNS announce + UDP fallback on the server; `GET /.well-known/video-tool` | a second process on the LAN lists the server within 2 s | `tests/test_discovery.py` (loopback multicast) |
| **CS4 Thin client** | `client/desktop/` connection screen, saved servers, keychain, same-computer auto start; the Python bootstrap moves to the server installer | the client installs and runs on a computer with no Python, pairs, and makes a video on the server | `client/studio/e2e/connect.mjs`; a two-computer run logged in evidence |
| **CS5 Files** | resumable uploads (chunks + offset) and streamed downloads; upload progress in the New flow | a 1 GB podcast uploads over Wi-Fi and survives a dropped connection | `tests/test_upload_resume.py` |
| **CS6 MCP over the network** | `.mcp.json` template for a remote server; the Studio's *Use your own AI assistant* shows the remote form | Claude Code on the client plans a video on the server | one live run logged |
| **CS7 Repo layout** | move folders to `client/` and `server/`; fix paths, CI and docs | `check_docs.py` clean, every suite passes | CI |

**Progress (2026-10-31).** CS1 and CS2 are built together, because a Studio listening beyond loopback without a token is not safe to ship.
- `vt server` ([server/vt/server/serve.py](../../server/vt/server/serve.py)) runs the Studio, the pipeline and the engine contract (`/.well-known/vt-engine`, `/v1/*`, `/gw/*`) on one
  port (8765). It uses one key, the hub identity, so pairing survives restarts. One pairing code serves both `/api/pair` (Studio clients; sets the `vt_token`
  cookie) and `/v1/pair` (engine clients). `vt engine pair --port 8765` prints a new code.
- `vt studio` is now `vt server --host 127.0.0.1` without starting engines. With that host, nothing changes for the desktop app.
- The guard is ASGI middleware, so it covers websockets too. It requires a Bearer header, the cookie or `?token=` on `/api`, `/ws` and `/media` from other
  computers. Loopback is exempt unless a forwarding header shows a proxy or tunnel sent the request.
- Verified: `tests/test_server_merge.py` and `tests/test_server_auth.py`; a live `vt server` probed over the LAN address (401 without a key, 200 with the
  cookie, codes work once).
- Not yet: `vt engine run` (port 8790) and the Studio's *Share this computer's engines* panel still run the old separate hub. They become aliases of
  `vt server` in CS4, together with the pairing screen in the Studio page. Tokens are one key per server, not per client. Revoking one client means
  `hub.reset_key()`, and then every client pairs again.

**Progress: CS3 and the first part of CS4 (2026-10-31).**
- Discovery ([server/vt/server/discovery.py](../../server/vt/server/discovery.py)): `vt server` announces `_videotool._tcp` (zeroconf) and answers `VIDEO-TOOL? 1` on UDP 8767
  with its card. `vt servers` and `GET /api/servers` list what answers. The desktop app asks by UDP broadcast on every IPv4 network of the computer
  ([client/desktop/discover.js](../../client/desktop/discover.js)), so it needs no Python. Verified by `tests/test_discovery.py` (including a real mDNS announce
  heard on loopback) and a live run: the Node client found the Python server on the LAN and Tailscale addresses.
- Engine placement: `vt server --comfy/--ollama/--voicestudio auto|existing|own|off`
  ([server/vt/engines/placement.py](../../server/vt/engines/placement.py)), and the same choice on the Engines page. *Existing* uses a service already on its usual
  ports and never starts, stops or changes it. *Own* runs our copy on its own port (Ollama 11444+, ComfyUI 8288+), so both can share one computer.
- Pairing without commands: a browser on another computer gets the Studio page and a **Connect** screen (`client/studio/src/Pair.tsx`) that asks for the
  code. The server's Engines page shows **This server** with its addresses and a **New pairing code** button (`POST /api/server/code`, only from the
  server computer itself).
- Desktop app: on first start it asks where to run (`client/desktop/connect.html`): this computer (the old behaviour), a server found on the network, or a
  typed address. It remembers the choice, and File > Connect to another server changes it.
- Each paired device gets its own token (`server/vt/server/clients.py`, only hashes kept). The This server card lists them with **Revoke**; the server key
  still serves engine clients.
- `vt server --start-at-login` and the card's **Start by itself** register a login service (systemd user unit, launchd agent, or Windows task)
  with the same engines and port. On Linux, starting at boot with nobody logged in also needs `loginctl enable-linger` once; the owner decides.
- Two-computer run (2026-10-31): a Linux GPU server (Ubuntu, V100 + RTX 3060; ComfyUI on 8188 and 8189, Ollama and VoiceStudio already running as
  system services) was set up by `scripts/setup.sh --skip-model` in a separate folder, with its own uv, Python, cache and Node. `vt server` used the
  existing services untouched (ComfyUI 8188 as main, 8189 as worker) on port 8767, because 8765 was taken. From the Windows PC, `vt servers` found
  it. The API refused it before pairing (401), served the page (200), paired once with the code, and then reported all three engines healthy.
- Still to do in CS4: the Python bootstrap moved out of the client installer; the Electron
  flow checked on a computer without Python.

**Progress: CS5 (2026-10-31).** Files of 8 MB or more go up in 8 MB chunks ([server/vt/server/uploads.py](../../server/vt/server/uploads.py)). After a drop
the Studio asks the server how far it got and carries on, also after a page reload (the upload id is kept per file in the browser). A chunk sent
twice is refused with the right offset, so nothing is doubled. `POST /api/inspect` and `POST /api/projects` take the finished upload by id, so a
video that is looked at first is sent only once. Unused uploads are removed after two days. `client/studio/src/api.ts` `upload()` does this by itself,
so the New flow and the Shorts page did not change. Verified by `tests/test_upload_resume.py`. Not yet verified: a real 1 GB file over Wi-Fi with
the connection cut.

**Progress: CS6 (2026-10-31).** `vt server` serves the MCP tools at `/mcp` on its own port (`install_mcp` in
[server/vt/server/serve.py](../../server/vt/server/serve.py)), only when it listens beyond this computer. `/mcp` always needs a key, even from this computer:
the tools can do anything, and a web page could otherwise reach them through localhost. On the server itself the stdio form needs none. The AI
assistants page (on another device, or on the server under *An assistant on another computer*) makes a key for one assistant and shows the
`claude mcp add --transport http ...` line and the `.mcp.json`. Each key is a paired device, revoked in the same list. On a remote device the
page hides the stdio snippets, which only work on the server. Verified by `tests/test_mcp_network.py` (a real MCP client over HTTP) and a live run:
from the Windows PC, an MCP client listed the GPU server's 34 tools and called `list_projects`.

## 5. Risks

| Risk | Mitigation |
|---|---|
| The token leaks (a shared screenshot, a pasted `.mcp.json`) | tokens are per client and can be revoked in the server's Settings; the server shows the list of paired clients |
| mDNS is blocked (corporate Wi-Fi, some routers) | UDP broadcast fallback, then the typed address |
| A server reachable from the internet through a tunnel | the same token rules; the docs recommend an access policy in front of it, as for VoiceStudio |
| Two people edit the same project | the project lock already used by MCP edits; the second editor sees it read-only |
