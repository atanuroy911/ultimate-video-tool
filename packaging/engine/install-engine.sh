#!/usr/bin/env bash
# Video Tool Engine: installs this computer as the server for Video Tool (Linux and macOS).
#
#   ./install-engine.sh                       # install, download Ollama + ComfyUI + the picture models, start nothing
#   ./install-engine.sh --service             # ...and start the engine at every login / boot
#   ./install-engine.sh --check               # install the program only and prove it starts (no models); used by the build
#
# Options:  --dir DIR  --engines ollama,comfy  --bundles pictures,clips  --models DIR  --port 8790
#           --no-setup (program only)  --service  --check  --python PATH (use this Python instead of installing one with uv)
# Nothing needs administrator rights. Everything goes under DIR (default ~/.local/share/video-tool-engine).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${VT_ENGINE_DIR:-$HOME/.local/share/video-tool-engine}"
ENGINES="ollama,comfy"; BUNDLES="pictures"; MODELS=""; PORT=8790
NO_SETUP=0; SERVICE=0; CHECK=0; PY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --engines) ENGINES="$2"; shift 2 ;;
    --bundles) BUNDLES="$2"; shift 2 ;;
    --models) MODELS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --python) PY="$2"; shift 2 ;;
    --no-setup) NO_SETUP=1; shift ;;
    --service) SERVICE=1; shift ;;
    --check) CHECK=1; NO_SETUP=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
APP="$DIR/app"; DATA="$DIR/data"; VENV="$DIR/venv"
mkdir -p "$DIR" "$DATA"

say "1/4 Copying the program to $APP"
if [ "$(cd "$HERE" && pwd)" != "$APP" ]; then
  rm -rf "$APP"; mkdir -p "$APP"
  (cd "$HERE" && tar -cf - --exclude='__pycache__' .) | (cd "$APP" && tar -xf -)
fi

if [ -z "$PY" ]; then
  say "2/4 Python 3.11 and the locked packages (uv)"
  UV="$(command -v uv || true)"
  if [ -z "$UV" ]; then
    echo "uv is not installed; getting it (astral.sh) into $DIR/bin"
    mkdir -p "$DIR/bin"
    curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR="$DIR/bin" UV_NO_MODIFY_PATH=1 sh
    UV="$DIR/bin/uv"
  fi
  (cd "$APP" && UV_PROJECT_ENVIRONMENT="$VENV" "$UV" sync --frozen --no-dev --python 3.11)
  PY="$VENV/bin/python"
else
  say "2/4 Using the Python you gave: $PY"
fi

export VT_DATA="$DATA" PYTHONIOENCODING=utf-8 PYTHONPATH="$APP"
vt() { (cd "$APP" && "$PY" -m vt.cli "$@"); }

say "3/4 What this computer can do"
vt engine plan --engines "$ENGINES" --bundles "$BUNDLES" ${MODELS:+--models "$MODELS"}

if [ "$NO_SETUP" = "0" ]; then
  say "Downloading and installing (can be stopped and started again: it resumes)"
  vt engine setup --yes --engines "$ENGINES" --bundles "$BUNDLES" ${MODELS:+--models "$MODELS"}
fi

cat > "$DIR/run-engine.sh" <<EOF
#!/usr/bin/env bash
export VT_DATA="$DATA" PYTHONIOENCODING=utf-8 PYTHONPATH="$APP"
cd "$APP" && exec "$PY" -m vt.cli engine run --port $PORT --engines "$ENGINES" "\$@"
EOF
chmod +x "$DIR/run-engine.sh"

if [ "$CHECK" = "1" ]; then
  say "4/4 Proving it starts"
  (cd "$APP" && "$PY" -m vt.cli engine run --port "$PORT" --engines "" --no-start > "$DIR/check.log" 2>&1 & echo $! > "$DIR/check.pid")
  ok=0
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:$PORT/.well-known/vt-engine" > "$DIR/check.json" 2>/dev/null; then ok=1; break; fi
    sleep 1
  done
  kill "$(cat "$DIR/check.pid")" 2>/dev/null || true
  if [ "$ok" != "1" ]; then echo "the engine did not answer; log:" >&2; cat "$DIR/check.log" >&2; exit 1; fi
  cat "$DIR/check.json"; echo
  grep -q '"engine_server"' "$DIR/check.json" || { echo "the answer is not an engine document" >&2; exit 1; }
  echo "OK: the engine starts and answers."
  exit 0
fi

if [ "$SERVICE" = "1" ]; then
  say "4/4 Starting it automatically"
  vt engine service --install --port "$PORT"
else
  say "4/4 Done"
fi

cat <<EOF

The engine is installed in $DIR.
Start it:        $DIR/run-engine.sh
It prints an address and a pairing code. On the computer with the Video Tool window:
Settings, Engines, "Another Video Tool computer", then the address and the code.
A new code later:  (engine running)  cd "$APP" && VT_DATA="$DATA" "$PY" -m vt.cli engine pair
EOF
