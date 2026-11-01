#!/usr/bin/env bash
# One-time setup for Video Tool on Linux and macOS (scripts/setup.ps1 on Windows). Safe to re-run: every step is skipped when already done.
#
#   scripts/setup.sh                 full setup
#   scripts/setup.sh --skip-model    do not download the Bangla speech model now (the app downloads it on first use)
#
# Needs: FFmpeg on PATH. Python is not needed: uv (downloaded into .tools/) installs its own Python 3.11 for .venv; Node 20+ with npm is
# used from PATH, or downloaded into bin/node when missing.
# Nothing is installed outside this folder, except what uv caches. To keep that here too (a server with a separate data disk):
#   UV_PYTHON_INSTALL_DIR=/disk/vt/python UV_CACHE_DIR=/disk/vt/cache VT_DATA=/disk/vt/data scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
SKIP_MODEL=0
for a in "$@"; do [ "$a" = "--skip-model" ] && SKIP_MODEL=1; done
step() { printf '\n== %s\n' "$1"; }

step "Checking prerequisites"
# Node: the one on PATH when it is 20+ and has npm; otherwise our own copy in bin/node (the app looks there first, vt/util.py tool_dirs)
NODE_VERSION=22.22.1
[ -x bin/node/bin/npm ] && export PATH="$PWD/bin/node/bin:$PATH"
if ! command -v npm >/dev/null || [ "$(node -v 2>/dev/null | sed 's/^v//; s/\..*//')" -lt 20 ] 2>/dev/null; then
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) NP=linux-x64 ;; Linux-aarch64) NP=linux-arm64 ;; Darwin-arm64) NP=darwin-arm64 ;; Darwin-x86_64) NP=darwin-x64 ;;
    *) echo "Node.js 20 or newer with npm is required: https://nodejs.org"; exit 1 ;;
  esac
  echo "Downloading Node $NODE_VERSION into bin/node (nothing is installed system-wide)"
  rm -rf bin/node && mkdir -p bin/node
  curl -LsSf "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$NP.tar.gz" | tar -xz -C bin/node --strip-components=1
  export PATH="$PWD/bin/node/bin:$PATH"
fi
command -v ffmpeg >/dev/null || { echo "FFmpeg is required on PATH (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
echo "node $(node -v), $(ffmpeg -version | head -1)"

step "Python 3.11 and the locked packages"
UV=.tools/uv
if [ ! -x "$UV" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$PWD/.tools" UV_NO_MODIFY_PATH=1 sh
fi
# the GPU build that fits this computer: cu128 (RTX 50), cu124 (default), cu118 (old drivers) or cpu (vt/gpu_detect.py, standard library only)
FLAVOUR=$("$UV" run --no-project --python 3.11 python vt/gpu_detect.py 2>/dev/null || echo cpu)
case "$FLAVOUR" in cu128|cu124|cu118|cpu) ;; *) FLAVOUR=cpu ;; esac
echo "GPU build: $("$UV" run --no-project --python 3.11 python vt/gpu_detect.py --explain 2>/dev/null || echo "$FLAVOUR")"
"$UV" sync --frozen --extra dev --extra "$FLAVOUR" --python 3.11
PY=.venv/bin/python
"$PY" -c "import torch; print('torch', torch.__version__, '| GPUs:', [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] or 'none')"

step "Video renderer, fonts and icons"
(cd renderer && npm install --no-audit --no-fund && node scripts/build-fonts.mjs && node scripts/build-icons.mjs)
[ -f design/textures/paper-grain.png ] || "$PY" scripts/make_texture.py
[ -f assets/music/index.json ] || { step "Bundled music and sound effects"; "$PY" scripts/make_assets.py; }

step "Studio (web app)"
(cd studio && npm install --no-audit --no-fund && npm run build)

if [ "$SKIP_MODEL" = 0 ]; then
  step "Bangla speech model (about 3 GB download, converted once; can take 10-20 minutes)"
  HF_HUB_DISABLE_XET=1 "$PY" -m vt.cli models pull bn-medium
fi

step "System check"
"$PY" -m vt.cli doctor || true
printf '\nDone. Start the server with:  .venv/bin/python -m vt.cli server\n'
