#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ARGS=()
for arg in "$@"; do case "$arg" in --skip-model|--cpu-only) ;; *) ARGS+=("$arg");; esac; done
exec bash "$HERE/dev-install.sh" --role both "${ARGS[@]}"
