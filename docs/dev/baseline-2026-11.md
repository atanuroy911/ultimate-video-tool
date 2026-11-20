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
