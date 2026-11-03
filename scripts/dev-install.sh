#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT="${HOME}/.ultimate-video-tool-dev"
ARGS=("$@")
for ((i=0;i<${#ARGS[@]};i++)); do if [[ "${ARGS[$i]}" == --root ]]; then ROOT="${ARGS[$((i+1))]}"; fi; done
NODE=$(command -v node || true)
if [[ -n "$NODE" ]]; then
  if ! "$NODE" -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>22||a===22&&b>=12?0:1)'; then NODE=''; fi
fi
if [[ -z "$NODE" ]]; then
  VERSION=22.22.1
  case "$(uname -m)" in x86_64) ARCH=x64;; aarch64|arm64) ARCH=arm64;; *) echo 'Unsupported CPU architecture' >&2; exit 2;; esac
  ASSET="node-v${VERSION}-linux-${ARCH}.tar.xz"
  TOOLS="$ROOT/tools/node";NODE="$TOOLS/node-v${VERSION}-linux-${ARCH}/bin/node"
  if [[ ! -x "$NODE" ]]; then
    mkdir -p -- "$TOOLS"
    curl --fail --location --retry 3 "https://nodejs.org/dist/v${VERSION}/${ASSET}" -o "$TOOLS/$ASSET"
    curl --fail --location --retry 3 "https://nodejs.org/dist/v${VERSION}/SHASUMS256.txt" -o "$TOOLS/SHASUMS256.txt"
    (cd -- "$TOOLS"; awk -v file="$ASSET" '$2==file {print}' SHASUMS256.txt > selected-checksum.txt; test -s selected-checksum.txt; sha256sum -c selected-checksum.txt)
    tar -xJf "$TOOLS/$ASSET" -C "$TOOLS"
  fi
fi
exec "$NODE" "$SCRIPT_DIR/dev-install.mjs" "$@"
