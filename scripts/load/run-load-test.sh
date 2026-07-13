#!/usr/bin/env bash
# Run k6 load test profile (smoke|baseline|stress) against prepared environment.
#
# Usage:
#   PROFILE=smoke bash scripts/load/run-load-test.sh
#   PROFILE=baseline LOAD_TEST_DURATION=5m LOAD_TEST_VUS=2 bash scripts/load/run-load-test.sh
#   PROFILE=stress LOAD_TEST_STAGES="2m:5,4m:15,4m:30,2m:5" bash scripts/load/run-load-test.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_DIR="${ROOT}/infra/load-testing"
ENV_FILE="${LOAD_DIR}/.env.load"
COMPOSE_FILE="${LOAD_DIR}/docker-compose.load-testing.yml"
PROFILE="${PROFILE:-${1:-}}"

if [[ -z "${PROFILE}" ]]; then
  echo "Usage: PROFILE=smoke|baseline|stress bash scripts/load/run-load-test.sh" >&2
  exit 1
fi

case "${PROFILE}" in
  smoke|baseline|stress) ;;
  *)
    echo "Unsupported PROFILE='${PROFILE}'. Expected: smoke | baseline | stress" >&2
    exit 1
    ;;
esac

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run: bash scripts/load/prepare-load-test-env.sh" >&2
  exit 1
fi

if ! docker network inspect naming-check-net >/dev/null 2>&1; then
  docker network create naming-check-net >/dev/null
fi

bash "${ROOT}/scripts/load/verify-load-test-ready.sh"

echo "==> Running ${PROFILE} load test"
echo "    target: ${LOAD_TEST_BASE_URL:-from .env.load}"
echo "    vus: ${LOAD_TEST_VUS:-default}"
echo "    duration: ${LOAD_TEST_DURATION:-default}"
echo "    rps: ${LOAD_TEST_RPS:-default}"

docker compose -f "${COMPOSE_FILE}" \
  --env-file "${ENV_FILE}" \
  --profile load-test \
  run --rm \
  -e LOAD_TEST_PROFILE="${PROFILE}" \
  -e LOAD_TEST_VUS="${LOAD_TEST_VUS:-}" \
  -e LOAD_TEST_DURATION="${LOAD_TEST_DURATION:-}" \
  -e LOAD_TEST_RPS="${LOAD_TEST_RPS:-}" \
  -e LOAD_TEST_STAGES="${LOAD_TEST_STAGES:-}" \
  -e LOAD_TEST_ITERATION_SLEEP_SECONDS="${LOAD_TEST_ITERATION_SLEEP_SECONDS:-}" \
  -e LOAD_TEST_S1_WEIGHT="${LOAD_TEST_S1_WEIGHT:-}" \
  -e LOAD_TEST_S2_WEIGHT="${LOAD_TEST_S2_WEIGHT:-}" \
  -e LOAD_TEST_S3_WEIGHT="${LOAD_TEST_S3_WEIGHT:-}" \
  -e LOAD_TEST_S4_WEIGHT="${LOAD_TEST_S4_WEIGHT:-}" \
  -e K6_LOGO_FILE="${K6_LOGO_FILE:-}" \
  -e K6_FALLBACK_PREVIEW_PATH="${K6_FALLBACK_PREVIEW_PATH:-}" \
  -e K6_TEXT_TOP_K="${K6_TEXT_TOP_K:-}" \
  -e K6_LOGO_TOP_K="${K6_LOGO_TOP_K:-}" \
  k6 run "/scripts/${PROFILE}.js"

echo "Check Grafana → Naming Check → Load Testing for live metrics."
