# Baseline before PLAN-WORKBENCH (2026-11-20)

Measured on the laptop (Windows 11, RTX 4050 Laptop 6 GB), branch `workbench` at the commit after `a15e6c7`. Everything ran from `E:\UltimateVideoTool\` (uv, Python environment, scratch data). The GPU server was not used.

## Tests
| Suite | Result |
|---|---|
| `pytest -m "not slow"` (CPU build of torch) | **1,867 passed, 4 skipped, 1 failed**, 15 min 47 s |
| The one failure | `tests/test_gpu.py::test_torch_onnx_and_ctranslate2_share_the_gpu_in_one_process` asserts CUDA, and this environment has the CPU build of torch (`--extra cpu`, as CI uses). An environment difference, not a product bug. It needs the `gpu` marker (W3.2). |
| CI on GitHub, last run before this plan | 1,865 passed, 7 skipped |

## Studio
| Item | Value |
|---|---|
| `npm ci` | 19 s |
| `npm run build` | 7 s (3.4 s of it Vite) |
| `client/studio/dist` | 1,733 KB |
| `client/studio/src/pages/Review.tsx` | 651 lines |
| `client/studio/src/styles.css` | 1,118 lines |
| Distinct raw hex colours in `client/studio/src` | 223 |
| `server/vt/server/app.py` | 3,325 lines, 167 routes |

## Repository
| Item | Value |
|---|---|
| `git archive HEAD` (the tip, uncompressed) | 492.7 MB. Almost all of it is `docs/evidence` (6,556 files). W5.1 removes it. |
| `.git` | 196 MB (history stays: decision D5) |

## v1.0.0 installers (for the size comparisons in W9 and W12)
| File | Size |
|---|---|
| Client, Windows | 78.5 MB |
| Client, Linux .deb / AppImage | 72.2 / 103.6 MB |
| Server, Windows | 225.9 MB |
| Server, Linux .deb / AppImage | 181.7 / 252.1 MB |

## Screenshots (before)
`docs/dev/shots/before-editor-{1440x900,1280x720}-{light,dark}.png` (the editor on the sample project "reference") and `before-projects-1440x900-{light,dark}.png`. Taken with `scripts/dev/shot.mjs` against a scratch server on port 8771 (data in `E:\UltimateVideoTool\scratch\w0-data`) and the Studio dev server on port 5173.

## How to run things on this laptop
```bash
export UV_CACHE_DIR=E:/UltimateVideoTool/.uvcache UV_PYTHON_INSTALL_DIR=E:/UltimateVideoTool/.pythons UV_PROJECT_ENVIRONMENT=E:/UltimateVideoTool/venv-workbench
UV=/e/UltimateVideoTool/.tools/uv.exe
$UV run --project server pytest -m "not slow"                       # fast suite
VT_DATA=E:/UltimateVideoTool/scratch/<step> $UV run --project server vt studio --port 8771 --no-open     # scratch server
cd client/studio && VT_SERVER_URL=http://127.0.0.1:8771 npm run dev -- --port 5173 --strictPort           # the editor (open http://localhost:5173)
MSYS_NO_PATHCONV=1 VT_URL=http://localhost:5173 node scripts/dev/shot.mjs /p/reference <outPrefix> 1440x900   # screenshots
```
ffmpeg must be on PATH (the winget copy: `C:\Users\Roy\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin`). In Git Bash, put `MSYS_NO_PATHCONV=1` before any command that takes a URL path starting with `/`.

## 0.5.0 over 1.0.0 (W1.5, 2026-11-20)
Done on this laptop, both apps installed on E: (`E:\UVT-Client\Ultimate Video Tool`, `E:\UVT-Server\Ultimate Video Tool Server`; server data junction to `E:\UltimateVideoTool\ServerData`).
1. Installed the published **1.0.0** Windows installers (checksums verified against SHA256SUMS.txt), `/S /currentuser`, no `/D=`.
2. Built the 0.5.0 installers (`scripts/build_*_windows.sh`) and ran them over it with no uninstall: **client exit 0 in 8 s, server exit 0 in 55 s**. The installer did not refuse the lower number (no downgrade setting was needed). Both still on E:; Add/Remove Programs shows 0.5.0 only.
3. First start of the 0.5.0 server rebuilt its runtime from scratch (the 1.0.0 server had never been started here, so this is a first-run time, not an upgrade time): about 22 minutes to answer on port 8790, 6.2 GB under `ServerData`.
4. The 0.5.0 server installer is 205.2 MB (1.0.0: 225.9 MB), the client 78.5 MB (1.0.0: 78.5 MB). The server is smaller here than in the release, probably because the release build adds FFmpeg (see the release workflow); check when the next release is built.
5. Linux `.deb` was not tested (no WSL yet): W15.4.

## Gotcha on this laptop
The shell that runs Claude Code has `ELECTRON_RUN_AS_NODE=1`. An Electron app started from it behaves as plain Node ("bad option" and exits). Clear it first: `Remove-Item Env:ELECTRON_RUN_AS_NODE`.
