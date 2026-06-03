#!/usr/bin/env bash
# Backward-compatible wrapper; use setup-elk.sh directly.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export USE_DOCKER_EXEC=1
exec "${SCRIPT_DIR}/setup-elk.sh"
