"""Install the processing server on the GPU box the way a user would, from the built package, into a new folder in roy's home.

    GPU_PASS=... python scripts/lab/install_server_fresh.py [package.tar.gz]

Steps (all inside /home/roy/ultimate-video-tool-server; nothing else on the box is touched):
  1. upload and unpack the package
  2. install-engine.sh --no-setup   (Python 3.11 + the locked packages in the GPU build vt/gpu_detect.py picks; the existing ComfyUI and
     Ollama are used, so no engines or models are downloaded)
  3. the renderer's Node packages (the box's own Node 22)
  4. run-server.sh and a user service that starts the server at login (port 8790, existing ComfyUI 8188 and Ollama 11434)
The install runs in the background on the box; this script prints the log path and returns.
"""
import os
import sys
from pathlib import Path

import paramiko

ROOT = "/home/roy/ultimate-video-tool-server"
pkg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "dist/fresh-2026-11-03/video-tool-engine-1.0.0.tar.gz"
INSTALL = r"""#!/bin/bash
set -euo pipefail
ROOT=/home/roy/ultimate-video-tool-server
cd "$ROOT"
mkdir -p pkg tmp
tar -xzf package.tar.gz -C pkg --strip-components=1
export TMPDIR="$ROOT/tmp" PATH="$ROOT/node/bin:$HOME/.local/bin:$PATH"
if [ ! -x "$ROOT/node/bin/npm" ]; then          # a private Node with npm, checksum-verified (the box's own Node may come without npm)
  V=v22.22.1; mkdir -p node dl
  curl -fsSL -o dl/SHASUMS256.txt https://nodejs.org/dist/$V/SHASUMS256.txt
  curl -fsSL -o dl/node.tar.xz https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz
  [ "$(grep "node-$V-linux-x64.tar.xz" dl/SHASUMS256.txt | awk '{print $1}')" = "$(sha256sum dl/node.tar.xz | awk '{print $1}')" ] || { echo "Node checksum mismatch"; exit 1; }
  tar -xJf dl/node.tar.xz -C node --strip-components=1; rm -rf dl
fi
[ -d "$ROOT/venv" ] || bash pkg/install-engine.sh --dir "$ROOT" --no-setup
cd "$ROOT/app/renderer"
npm ci --no-audit --no-fund --cache "$ROOT/cache/npm"
[ -f "$ROOT/app/design/fonts/fonts.css" ] || node scripts/build-fonts.mjs
[ -f "$ROOT/app/design/icons/lucide.json" ] || node scripts/build-icons.mjs
cd "$ROOT"
cat > run-server.sh <<'EOS'
#!/bin/bash
set -euo pipefail
ROOT=/home/roy/ultimate-video-tool-server
export VT_DATA="$ROOT/data" TMPDIR="$ROOT/tmp" PATH="$ROOT/node/bin:/usr/bin:/bin" HYPERFRAMES_NO_TELEMETRY=1 PYTHONIOENCODING=utf-8
export CUDA_VISIBLE_DEVICES=GPU-a1b5ab18-d194-1ae3-a17f-4561c4f0cd7d   # the RTX 3060 only: the owner's V100 is for their own work
cd "$ROOT/app"
exec "$ROOT/venv/bin/python" -m vt.cli server --host 0.0.0.0 --port 8790 --name "Ultimate Video Tool Server" \
  --comfy existing --comfy-url http://127.0.0.1:8188 --ollama existing --ollama-url http://127.0.0.1:11434 --voicestudio off
EOS
chmod +x run-server.sh
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ultimate-video-tool.service" <<EOS
[Unit]
Description=Ultimate Video Tool Server
After=network-online.target
[Service]
ExecStart=$ROOT/run-server.sh
Restart=on-failure
[Install]
WantedBy=default.target
EOS
systemctl --user daemon-reload
systemctl --user enable --now ultimate-video-tool.service
printf 'INSTALL_OK\n'
"""


def main() -> None:
    if not pkg.exists():
        raise SystemExit(f"no package at {pkg}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.123.47", username="roy", password=os.environ["GPU_PASS"], look_for_keys=False, allow_agent=False, timeout=20)
    s = c.open_sftp()
    try:
        try:
            s.lstat(ROOT)
            raise SystemExit(f"{ROOT} already exists; refusing to install over it")
        except FileNotFoundError:
            s.mkdir(ROOT, mode=0o700)
        s.put(str(pkg), ROOT + "/package.tar.gz")
        with s.file(ROOT + "/install.sh", "w") as f:
            f.write(INSTALL)
        s.chmod(ROOT + "/install.sh", 0o700)
        _, out, _ = c.exec_command(f"nohup bash {ROOT}/install.sh > {ROOT}/install.log 2>&1 < /dev/null & echo started $!")
        print(out.read().decode().strip(), "| log:", ROOT + "/install.log")
    finally:
        s.close()
        c.close()


if __name__ == "__main__":
    main()
