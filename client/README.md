# Ultimate Video Tool Client

The video workspace lives here: the editor in `studio/`, and the native desktop client with its Claude/Codex companion in `desktop/`.

This product has no Python environment, model installer or rendering backend. It serves its own editor files from a protected loopback HTTP service and forwards API/media/WebSocket traffic to the selected processing server. Each server has an isolated desktop session for pairing.

From the repository root:

```powershell
./scripts/dev-install.ps1 -Role client -ServerUrl http://192.168.123.47:8790
```

```sh
bash scripts/dev-install.sh --role client --server-url http://192.168.123.47:8790
```

Build the editor with `npm --prefix client/studio run build`, and the client installer with `npm --prefix client/desktop run dist`. Install the server separately for local processing.
