#!/usr/bin/env bash
# Start (or restart) VoiceStudio on the GPU machine: the RTX 3060, data on the big drive, API key from a private env file.
# A versioned copy of what runs at /mnt/bigdata/video-tool/voicestudio/run.sh. See docs/ops/voicestudio-server.md.
set -euo pipefail
BASE=${VOICESTUDIO_BASE:-/mnt/bigdata/video-tool/voicestudio}
IMAGE=${VOICESTUDIO_IMAGE:-ghcr.io/debpalash/voicestudio:stable}
GPU_INDEX=${VOICESTUDIO_GPU:-1}                    # 1 = RTX 3060 (ComfyUI keeps the V100 busy)
HOST_NAME=${VOICESTUDIO_HOST:-voice.atanusroy.com}
ENVF="$BASE/voicestudio.env"
mkdir -p "$BASE/data"
if [ ! -f "$ENVF" ]; then                          # the key is made once, readable by this user only, and never printed
  ( umask 077; printf 'OMNIVOICE_API_KEY=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > "$ENVF" )
fi
docker rm -f omnivoice >/dev/null 2>&1 || true
# GPU by device passthrough: the NVIDIA container toolkit is not installed (installing it restarts Docker, and with it every other container here)
docker run -d --name omnivoice --restart unless-stopped \
  --device "/dev/nvidia${GPU_INDEX}" --device /dev/nvidiactl --device /dev/nvidia-uvm --device /dev/nvidia-uvm-tools \
  -v /usr/lib/x86_64-linux-gnu/libcuda.so.1:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro \
  -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro \
  -p 0.0.0.0:3900:3900 --env-file "$ENVF" \
  -e OMNIVOICE_SERVER_MODE=1 -e OMNIVOICE_ANALYTICS_DISABLED=1 -e OMNIVOICE_GENERATE_TIMEOUT_S=900 \
  -e OMNIVOICE_ALLOWED_HOSTS="$HOST_NAME" -e OMNIVOICE_PUBLIC_API_BASE="https://$HOST_NAME" -e OMNIVOICE_ALLOWED_ORIGINS="https://$HOST_NAME" \
  -v "$BASE/data:/app/omnivoice_data" \
  "$IMAGE"
echo "started omnivoice on GPU $GPU_INDEX; wait for: curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3900/health"
