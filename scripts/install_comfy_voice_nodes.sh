#!/usr/bin/env bash
# Put the voice models on the ComfyUI server: Breeze TTS 2 and OmniVoice as ComfyUI custom node packs, with their weights on the big drive.
# Run this ON THE GPU MACHINE as the user that runs ComfyUI (roy). It is safe to run twice. Read docs/ops/comfyui-voice-nodes.md first.
#
# Why a script and not a click: both packs are third-party code that runs inside ComfyUI, so a person (or an agent the owner has allowed to) runs it on purpose.
# What it does, in order:
#   1. saves the current Python package list (so it can be undone),
#   2. clones the two node packs into ComfyUI's custom_nodes folder (shallow),
#   3. installs their small requirements with PyTorch, torchaudio and transformers PINNED to what is installed (a node pack must never change the PyTorch the V100 needs),
#   4. starts a second ComfyUI on the RTX 3060 (port 8189) for the models that need bf16 (Breeze), sharing the same models, nodes and folders,
#   5. waits until both ComfyUI servers list the new nodes.
# Weights download the first time a workflow runs (Breeze: about 6.5 GB bf16; OmniVoice: about 2 to 4 GB) into the models folder on the big drive.
set -euo pipefail

if [ "${SUDO_PASS_STDIN:-}" = 1 ]; then IFS= read -r SUDO_PASS; fi      # an agent pipes the password in on stdin (never on the command line)
S() {                                    # sudo: with SUDO_PASS set the password is piped in (no terminal needed); otherwise a normal sudo that asks
  if [ -n "${SUDO_PASS:-}" ]; then printf '%s\n' "$SUDO_PASS" | sudo -S -p "" "$@"; else sudo "$@"; fi
}
BASE=${VT_BASE:-/mnt/bigdata/video-tool}
APP=${COMFY_APP:-/home/roy/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI}
VENV="$BASE/comfy-venv"
BK="$BASE/backups"
CN="$APP/custom_nodes"

mkdir -p "$BK"
test -x "$VENV/bin/python" || { echo "no ComfyUI environment at $VENV"; exit 1; }
"$VENV/bin/pip" freeze > "$BK/comfy-venv-freeze-before-voice-$(date +%Y%m%d-%H%M).txt"

cd "$CN"
[ -d ComfyUI-Breeze-TTS-2 ]   || git clone --depth 1 https://github.com/saganaki22/ComfyUI-Breeze-TTS-2
[ -d ComfyUI-OmniVoice-TTS ]  || git clone --depth 1 https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS

# constraints: keep the installed PyTorch family and numpy exactly as they are
"$VENV/bin/python" - <<'PY' > "$BK/voice-constraints.txt"
import importlib.metadata as m
for name in ("torch", "torchvision", "torchaudio", "numpy", "transformers", "safetensors", "huggingface_hub", "tokenizers"):
    try:
        print(f"{name}=={m.version(name)}")
    except m.PackageNotFoundError:
        pass
PY
for pack in ComfyUI-Breeze-TTS-2 ComfyUI-OmniVoice-TTS; do
  if [ -f "$pack/requirements.txt" ]; then
    "$VENV/bin/pip" install -r "$pack/requirements.txt" -c "$BK/voice-constraints.txt"
  fi
done
# the environment runs Python 3.14, which dropped the standard `audioop` module that pydub (used by OmniVoice) imports: install the backport
"$VENV/bin/pip" install audioop-lts -c "$BK/voice-constraints.txt"
# OmniVoice's own package is installed without dependencies, as its README says, so PyTorch stays put
[ -f ComfyUI-OmniVoice-TTS/install.py ] && (cd ComfyUI-OmniVoice-TTS && "$VENV/bin/python" install.py || true)

# the second ComfyUI, on the RTX 3060 (GPU 1): a copy of the main unit with another port and device
if [ ! -f /etc/systemd/system/comfyui-audio.service ]; then
  UNITFILE=$(mktemp)
  cat > "$UNITFILE" <<UNIT
[Unit]
Description=ComfyUI (voices, RTX 3060)
After=network.target
RequiresMountsFor=$BASE/comfyui $BASE/comfy-venv

[Service]
Type=simple
User=roy
WorkingDirectory=$(dirname "$APP")
Environment=CUDA_DEVICE_ORDER=PCI_BUS_ID
Environment=CUDA_VISIBLE_DEVICES=1
Environment=HF_HOME=$BASE/comfyui/cache/huggingface
Environment=TORCH_HOME=$BASE/comfyui/cache/torch
Environment=XDG_CACHE_HOME=$BASE/comfyui/cache/xdg
ExecStart=$VENV/bin/python $APP/main.py --listen 0.0.0.0 --port 8189 --enable-cors-header --extra-model-paths-config $BASE/comfyui/extra_model_paths.yaml --input-directory $BASE/comfyui/input --output-directory $BASE/comfyui/output --temp-directory $BASE/comfyui/temp-audio --user-directory $BASE/comfyui/user
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
  S cp "$UNITFILE" /etc/systemd/system/comfyui-audio.service
  rm -f "$UNITFILE"
  S systemctl daemon-reload
fi
mkdir -p "$BASE/comfyui/temp-audio"
S systemctl enable --now comfyui-audio
S systemctl restart comfyui           # the main one picks up the new nodes too (a few seconds)

for port in 8188 8189; do
  for i in $(seq 1 60); do
    if curl -s "http://127.0.0.1:$port/object_info" | "$VENV/bin/python" -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'BreezeTTS2VoiceDesign' in d else 1)" 2>/dev/null; then echo "port $port: Breeze nodes are listed"; break; fi
    sleep 5
  done
done
echo "done. The next step is on the PC: Settings, Engines, ComfyUI, add the worker http://<this machine>:8189 and press Test."
