#!/usr/bin/env bash
# Backward-compatible wrapper for smoke profile.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROFILE=smoke bash "${ROOT}/scripts/load/run-load-test.sh"
