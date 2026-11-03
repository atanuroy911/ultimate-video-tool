# Agent-friendly development installation

Clone or download this repository first. Its independent products are `client/` and `server/`. Run the entry point for your operating system from the checkout; no administrator installation is needed for the private language runtimes.

## Windows

```powershell
./scripts/dev-install.ps1 -Role both
./scripts/dev-install.ps1 -Role client -ServerUrl http://192.168.123.47:8790
./scripts/dev-install.ps1 -Role server -NoLaunch
./scripts/dev-install.ps1 -Action Update -Role both -NoLaunch
./scripts/dev-install.ps1 -Action Check -Role both
```

Use `-Root` for a different private environment/data location and `-Source` for another checkout. `-NoUpdate` builds existing source without fetching changes. `-NoShortcuts` skips Start entries. Windows Start contains separate development launchers after installation.

## Linux

```sh
bash scripts/dev-install.sh --role both
bash scripts/dev-install.sh --role client --server-url http://192.168.123.47:8790
bash scripts/dev-install.sh --role server --no-launch
bash scripts/dev-install.sh --action update --role both --no-launch
bash scripts/dev-install.sh --action check --role both
```

Use `--root`, `--source`, `--no-update` and `--no-shortcuts` for the corresponding controls. Linux Applications contains separate development launchers. Desktop Linux still needs its normal GTK/system graphics libraries and a supported application sandbox; the scripts do not weaken system security policies or install operating-system packages.

## What the scripts do

- Reuse a supported Node, or download a private Node 22 runtime from nodejs.org and verify its SHA-256 against the vendor manifest.
- For the client, install only its JavaScript dependencies and build its editor. No Python/server environment is prepared in client-only mode.
- For the server, prepare uv/Python and the locked CPU dependency set in the chosen private root, and install server renderer/manager dependencies. ComfyUI/Ollama and model installation remain explicit actions in server management; existing engines are not replaced.
- Keep development data, credentials and control state separate from production client/server installations.
- Create launchers. They check for source updates at most every four hours, use fast-forward Git updates only, rebuild after an update and preserve local edits by skipping Git pulls in a dirty checkout. Source archives without Git can be installed, but cannot update themselves through Git.
- Write `install-state.json` beneath the private root, and print JSON status at the end. `Check` reports readiness without installing application dependencies. `-NoLaunch` / `--no-launch` is suitable for unattended setup by an agent.

The default private root is `%LOCALAPPDATA%/UltimateVideoToolDev` on Windows and `~/.ultimate-video-tool-dev` on Linux. Server Python is in `env/server`, processing data in `data/server`, and desktop state in `state/client` and `state/server`.

A development source install is distinct from the native release installers. Release products build independently with `npm --prefix client/desktop run dist` and `npm --prefix server/desktop run dist`.
