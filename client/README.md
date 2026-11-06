# Ultimate Video Tool Client

The video workspace lives here: the editor in `studio/`, and the native desktop client with its Claude/Codex companion in `desktop/`.

This product has no Python environment, model installer or rendering backend. It serves its own editor files from a protected loopback HTTP service and forwards API/media/WebSocket traffic to the selected processing server. Each server has its own isolated desktop session. A server on your network needs only its address: no code, no key.

From the repository root:

```powershell
./scripts/dev-install.ps1 -Role client -ServerUrl http://192.168.123.47:8790
```

```sh
bash scripts/dev-install.sh --role client --server-url http://192.168.123.47:8790
```

Build the editor with `npm --prefix client/studio run build`, and the client installer with `npm --prefix client/desktop run dist`. Install the server separately for local processing.

## Command line

Everything the connect window does can be done without it (for scripts and for assistants setting a computer up):

```powershell
& "$env:LOCALAPPDATA\Programs\Ultimate Video Tool\Ultimate Video Tool.exe" --server=192.168.123.47
```

- `--server=<address>` connects to that processing server. The address is all it needs (the usual port is added when you leave it out).
- Use the `--name=value` form. The app is started or, if it is already open, it is handed the arguments. Progress and errors are written to `%APPDATA%\Video Tool\desktop.log`.
- The space-separated form (`--server <address>`) can make the Electron runtime exit before the app reads it: use the `=` form.
- Started from a VS Code terminal, clear `ELECTRON_RUN_AS_NODE` first (`Remove-Item Env:ELECTRON_RUN_AS_NODE`), or the app runs as plain Node and exits at once.
- On the server: `vt system` (how busy it is), `vt gpu` / `vt gpu allow <cards|all|none>` (which graphics cards Video Tool may use) / `vt gpu set render <card>` (which card each job uses).
