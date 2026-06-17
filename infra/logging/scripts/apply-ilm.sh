#!/bin/sh
# Backward-compatible wrapper; runs index maintenance via docker exec on the host.
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export USE_DOCKER_EXEC=1
exec "${SCRIPT_DIR}/maintain-indices.sh"
