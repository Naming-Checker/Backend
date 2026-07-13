#!/usr/bin/env bash
# Run a short k6 smoke load test against the prepared environment.
#
# Usage:
#   bash scripts/load/run-smoke-load-test.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_DIR="${ROOT}/infra/load-testing"
ENV_FILE="${LOAD_DIR}/.env.load"
COMPOSE_FILE="${LOAD_DIR}/docker-compose.load-testing.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run: bash scripts/load/prepare-load-test-env.sh" >&2
  exit 1
fi

bash "${ROOT}/scripts/load/verify-load-test-ready.sh"

echo "==> Running k6 smoke load test"
docker compose -f "${COMPOSE_FILE}" \
  --env-file "${ENV_FILE}" \
  --profile load-test \
  run --rm k6 run /scripts/smoke.js

echo "Check Grafana → Naming Check → Services for RPS/latency during the run."
