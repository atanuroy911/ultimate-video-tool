#!/usr/bin/env bash
# Container start: make sure Ollama, ComfyUI and the models are in the /data volume (a no-op once they are), then run the command given.
#   VT_ENGINES=ollama,comfy        which engines to set up and offer
#   VT_BUNDLES=pictures            ComfyUI model sets: pictures, clips
#   VT_SETUP=0                     skip the download step (the volume is already filled)
set -euo pipefail
ENGINES="${VT_ENGINES:-ollama,comfy}"
BUNDLES="${VT_BUNDLES:-pictures}"

if [ "${VT_SETUP:-1}" != "0" ] && [ "${1:-}" = "engine" ] && [ "${2:-}" = "run" ]; then
  echo "Checking Ollama, ComfyUI and the models in /data (downloads only what is missing)"
  vt engine setup --yes --engines "$ENGINES" --bundles "$BUNDLES" || echo "setup did not finish: the engine starts with what is there; start the container again to resume"
fi

if [ "${1:-}" = "engine" ] && [ "${2:-}" = "run" ]; then
  exec vt engine run --host 0.0.0.0 --engines "$ENGINES" "${@:3}"
fi
exec vt "$@"
