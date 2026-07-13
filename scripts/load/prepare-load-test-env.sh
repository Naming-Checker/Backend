#!/usr/bin/env bash
# Prepare the load testing environment on the test stand or locally.
#
# Creates .env.load from example, ensures Docker network, pulls k6 image,
# and runs readiness checks.
#
# Usage (on test stand server after deploy):
#   cd /opt/naming-check-backend
#   bash scripts/load/prepare-load-test-env.sh
#
# Usage (local, backend on :8000):
#   LOAD_TEST_BASE_URL=http://127.0.0.1:8000 \
#   LOAD_TEST_ALLOWED_HOSTS=localhost,127.0.0.1 \
#   bash scripts/load/prepare-load-test-env.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_DIR="${ROOT}/infra/load-testing"
ENV_FILE="${LOAD_DIR}/.env.load"
EXAMPLE_FILE="${LOAD_DIR}/.env.load.example"
COMPOSE_FILE="${LOAD_DIR}/docker-compose.load-testing.yml"

echo "==> Preparing load test environment"
echo "    root: ${ROOT}"

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ ! -f "${EXAMPLE_FILE}" ]]; then
    echo "Missing ${EXAMPLE_FILE}" >&2
    exit 1
  fi
  cp "${EXAMPLE_FILE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} from example — review LOAD_TEST_BASE_URL and allowlist."
fi

# shellcheck disable=SC1090
set -a && source "${ENV_FILE}" && set +a

# Auto-detect test stand: backend container present → use internal Docker URL.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx naming-check-backend; then
  if [[ "${LOAD_TEST_BASE_URL:-}" == "http://naming-check-backend:8000" ]] || [[ -z "${LOAD_TEST_BASE_URL:-}" ]]; then
    export LOAD_TEST_BASE_URL="http://naming-check-backend:8000"
    export LOAD_TEST_VERIFY_URL="${LOAD_TEST_VERIFY_URL:-http://127.0.0.1:8000}"
    export LOAD_TEST_ALLOWED_HOSTS="${LOAD_TEST_ALLOWED_HOSTS:-localhost,127.0.0.1,naming-check-backend}"
    export GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"
    export PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
    echo "Detected test stand — k6 target ${LOAD_TEST_BASE_URL}, verify ${LOAD_TEST_VERIFY_URL}"
  fi
fi

# Persist auto-detected verify URL for host-side checks.
if [[ -f "${ENV_FILE}" && -n "${LOAD_TEST_VERIFY_URL:-}" ]]; then
  if ! grep -q '^LOAD_TEST_VERIFY_URL=' "${ENV_FILE}"; then
    echo "LOAD_TEST_VERIFY_URL=${LOAD_TEST_VERIFY_URL}" >> "${ENV_FILE}"
  fi
fi

if ! docker network inspect naming-check-net >/dev/null 2>&1; then
  echo "Creating docker network naming-check-net..."
  docker network create naming-check-net
else
  echo "Docker network naming-check-net already exists."
fi

echo "Pulling k6 image..."
docker pull grafana/k6:0.54.0

echo "Verifying k6 compose file..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" config >/dev/null

echo
echo "==> Running readiness checks"
bash "${ROOT}/scripts/load/verify-load-test-ready.sh"

echo
echo "==> Verifying metrics collection"
if bash "${ROOT}/scripts/load/verify-metrics-collection.sh"; then
  :
else
  echo "Metrics not fully ready — monitoring stack may need traffic. Continue after deploy stabilizes."
fi

echo
echo "==> Load test environment prepared"
echo "    Config: ${ENV_FILE}"
echo "    Run smoke test: bash scripts/load/run-smoke-load-test.sh"
echo "    Grafana (during test): ${GRAFANA_URL:-http://127.0.0.1:3000}"
echo "    Docs: docs/performance/load_test_environment.md"
