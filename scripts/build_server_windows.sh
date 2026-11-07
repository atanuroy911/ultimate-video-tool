#!/usr/bin/env bash
# Builds the Windows server installer with its icon embedded (the same way as build_client_windows.sh).
# electron-builder runs with signAndEditExecutable=false (this account cannot create the symlinks its signing tools need), which also skips
# the icon step, so the exe would have Electron's default icon. Here: build the unpacked app, embed build/icon.ico with rcedit, then pack that.
# Usage: scripts/build_server_windows.sh [output-dir]      (default: server/desktop/dist)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:-$root/server/desktop/dist}"
rcedit="$(ls -d "$LOCALAPPDATA"/electron-builder/Cache/winCodeSign/*/rcedit-x64.exe 2>/dev/null | head -1)"
[ -n "$rcedit" ] || { echo "rcedit-x64.exe not found in the electron-builder cache (run one electron-builder build first)"; exit 1; }
cd "$root/server/desktop"
npx electron-builder --win --dir --publish never -c.win.signAndEditExecutable=false -c.directories.output="$out"
"$rcedit" "$out/win-unpacked/Ultimate Video Tool Server.exe" --set-icon "$root/server/desktop/build/icon.ico"
npx electron-builder --win nsis -c.win.signAndEditExecutable=false --prepackaged "$out/win-unpacked" --publish never -c.directories.output="$out"
ls -la "$out"/*.exe
