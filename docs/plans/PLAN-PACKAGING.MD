# Packaging: the app, the engine, and the build that makes both

Owner's request (2026-10-28): GitHub Actions that compile the **client** and the **server**. If both are on the owner's PC they install on the same PC; the server can also be a different PC. The server downloads every model it needs and sets up Ollama, ComfyUI and the rest.

## 1. Two products, one codebase

| Product | Who installs it | What it is | Download |
|---|---|---|---|
| **Video Tool** (the app) | everyone | the window (Studio), the video pipeline, **and the ability to set the engines up on the same computer** (`vt/engines/installers.py`, the setup wizard) | `.exe` (Windows), `.dmg` (macOS), `.AppImage` / `.deb` (Linux), built with Electron from `desktop/` |
| **Video Tool Engine** (the server) | the owner of a GPU computer | no window. Downloads and starts Ollama and ComfyUI (and their models), and offers them to other computers at one address with one key | `video-tool-engine-<version>.zip` / `.tar.gz` (Windows, Linux, macOS), and the Docker image `ghcr.io/<owner>/video-tool-engine` |

Both run the **same code** (`vt/`). The engine package is that code without the Studio, the renderer and the designs: 218 files, under 1 MB, no models and no Python. The Python, the locked packages and the models are fetched on the target computer.

### Where each half runs
| Layout | What to do |
|---|---|
| **Everything on one computer** | Install **Video Tool**. First run: the setup wizard, "Set it up here" for Language AI and Pictures (`vt/engines/setup.py`). Nothing else. |
| **Window on one computer, engines on another** | On the GPU computer install the **Engine** package. On the other one install **Video Tool**, then Settings, Engines, "Another Video Tool computer": the address and the code the engine printed. Language AI and Pictures connect through the same key. |
| **One computer is both, and shares** | Install **Video Tool**; in Settings, Engines, "Share this computer", press Start sharing. A second computer pairs to it. "Start at login" keeps it running. |
| **Existing servers** (Ollama, ComfyUI, VoiceStudio already running somewhere) | Settings, Engines, "Connect to my server": each address by hand, as before. |

## 2. The Engine hub

`vt engine run` (code: `vt/engines/hub.py`, `vt/engines/server.py`):

```
other computer ──HTTP + key──►  gateway :8790  ──127.0.0.1──►  Ollama :11434
                                  /.well-known/vt-engine         ComfyUI :8188
                                  /v1/pair  /v1/health           VoiceStudio :3900 (when present)
                                  /v1/voice/*  /v1/asr/*
                                  /gw/<key>/<service>/...   (streamed reverse proxy)
```

* The services listen **only on 127.0.0.1**. Port 8790 is the one open port; everything behind it needs the key.
* The **key is made once** (`<data>/engine-hub.json`) so a restart does not unpair anyone. Each start prints a **pairing code that works once**; `vt engine pair` (or the Studio's "New code") makes another. Deleting `engine-hub.json` revokes every paired computer.
* Pairing returns the key and the list of services; the Studio saves **Ollama and ComfyUI as remote engines** at `http://<hub>/gw/<key>/ollama` and `.../comfy`, so every existing code path (`vt/llm.py`, `vt/comfy/client.py`) works unchanged: they only see a different base address. This is a deliberate trade: the key travels in the path, not a header, because those clients take a plain address.
* The first start asks the operating system's firewall for permission on port 8790 (Windows: allow private networks; Linux: `ufw allow 8790/tcp`).
* Not encrypted. Use it on your own network, or put a tunnel or VPN in front for the internet (the owner's `voice.atanusroy.com` already works this way).
* Commands: `vt engine plan | setup | run | pair | status | service`. `setup` is resumable and checksummed (the E5 installers); `service --install` writes a scheduled task (Windows), a user service (Linux) or a launch agent (macOS), no administrator rights.

Not in the gateway yet: a WebSocket route (ComfyUI's progress socket; the client polls instead), and VoiceStudio through the key (it keeps its own API key; connect it directly as before).

## 3. The build (GitHub Actions)

Two workflows in `.github/workflows/`:

| File | When | What |
|---|---|---|
| `ci.yml` | every push to `main`, every pull request, and called by the release | **Python tests** (`pytest -m "not slow"` on the locked packages, via `uv`); **Studio** (`tsc` and `vite build`); **Docs check**; **Engine package**: build it, unpack it as a user would, then on **Ubuntu and Windows** run the real install script (`uv` installs Python 3.11 and the locked packages) and prove `vt engine run` answers `/.well-known/vt-engine` |
| `release.yml` | a tag `v*`, or by hand (a manual run builds everything and publishes nothing) | runs `ci.yml` first; **writes the tag's version into every file** (`scripts/set_version.py`); builds the **app installers** on Windows, macOS and Linux; builds the **Engine package** and installs it again on Ubuntu and Windows from the downloaded artifact; builds the **Docker image** (pushed to ghcr.io only for a tag); then **one release** with every file and `SHA256SUMS.txt`. Nothing is published unless every part built. |

Files: `scripts/set_version.py`, `scripts/make_engine_package.py`, `packaging/engine/` (`install-engine.ps1`, `install-engine.sh`, `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `README-ENGINE.txt`).

### The Engine package, step by step (what the install script does)
1. Copy the program to `<dir>/app`.
2. `uv` (fetched from astral.sh if absent) installs **Python 3.11** and the **locked packages** (`uv sync --frozen`) into `<dir>/venv`.
3. `vt engine plan`: what this computer can do and what will be downloaded (nothing yet).
4. `vt engine setup --yes`: Ollama and a small language model; ComfyUI with its own Python and the PyTorch wheel for the card (cu126 for Volta, cu128 for Blackwell; `torch_index`); the picture models from `assets/comfy/model-manifest.json`, **resumable, size-checked, SHA-256-checked**.
5. Optional `--service`: start at login. Then `run-engine.cmd` / `run-engine.sh`.
`-Check` / `--check` stops after step 3 and starts the engine without services to prove it answers: this is what CI runs.

### Docker
The image holds the program and Python. The first start runs `vt engine setup` into the `/data` volume (Ollama, ComfyUI, models), later starts only check. `docker compose up -d`, then `docker compose logs engine` for the address and the code. GPU use needs the NVIDIA container toolkit.

## 4. What is proven and what is not (2026-10-28)

| Proven here | Evidence |
|---|---|
| The gateway forwards bodies, queries, streams and errors, refuses a wrong key, and answers 502 for a service that is down | `tests/test_hub.py` (real HTTP on loopback) |
| Pairing connects Ollama and ComfyUI through the key; choosing "use" leaves the rest alone | `tests/test_hub.py` |
| The key survives a restart; a new code only from the hub's own computer; the Studio starts/stops the hub (real subprocess) | `tests/test_hub.py` |
| Setup goes on after one engine fails; the start-at-login files for Windows, macOS and Linux | `tests/test_hub.py` |
| The package holds the server and none of the Studio; shell scripts have Unix line ends; the workflows are valid and wired so nothing publishes unless everything built; every script they call exists | `tests/test_packaging.py`, `actionlint` (no findings) |
| `vt engine run` with the real Ollama of this PC: the models list and a streamed chat (`qwen2.5:7b`, answer "OK") came back through `/gw/<key>/ollama/`; a wrong key got 401; the pairing code worked once (loopback, 2026-10-28) | run by hand, no log file |
| The package, unpacked, installs and starts on this PC with both `install-engine.ps1` and `install-engine.sh` (`-Check`), using this PC's existing Python | run 2026-10-28 |

| NOT proven | Why |
|---|---|
| The workflows have **never run on GitHub** | no push was made (that is the owner's step) |
| `uv sync --frozen` from the unpacked package on a clean computer (the CI job does this on the first push) | here the existing virtual environment was used |
| The Docker image build | no Docker on this PC; the CI job builds it |
| A real install of Ollama + ComfyUI + models on a clean computer | T-6 in `docs/TEST-PLAN.md` still open; CI does not download 26 GB |
| A second physical computer pairing over a real network | only loopback so far |
| Code signing, auto-update | not built; Windows and macOS warn on first open |

## 5. First-time setup of the repository (the owner's steps)
1. Create the GitHub repository and push (`git remote add origin ...`, `git push -u origin main`). **Large local files are ignored** by `.gitignore` (models, projects, `dist/`); check `git status` first, the working tree currently holds many untracked folders.
2. The `CI` workflow runs by itself. Fix whatever it finds: it has never run.
3. To release: `python scripts/set_version.py 1.0.0`, commit, `git tag v1.0.0`, `git push --tags`. The `Release` workflow does the rest; GitHub Packages must be allowed to publish (Settings, Actions, Workflow permissions: read and write).
4. For the Docker image to be public: GitHub, Packages, `video-tool-engine`, Package settings, Change visibility.
