#!/usr/bin/env bash
# Pre-flight checks before running load tests.
#
# Usage:
#   bash scripts/load/verify-load-test-ready.sh
#   LOAD_TEST_BASE_URL=http://127.0.0.1:8000 bash scripts/load/verify-load-test-ready.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_DIR="${ROOT}/infra/load-testing"
ENV_FILE="${LOAD_DIR}/.env.load"

failures=0

log_ok() { printf '  [OK] %s\n' "$1"; }
log_warn() { printf '  [WARN] %s\n' "$1"; }
log_fail() { printf '  [FAIL] %s\n' "$1"; failures=$((failures + 1)); }

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a && source "${ENV_FILE}" && set +a
fi

TARGET_URL="${LOAD_TEST_BASE_URL:-}"
VERIFY_URL="${LOAD_TEST_VERIFY_URL:-${TARGET_URL}}"
ALLOWED_HOSTS="${LOAD_TEST_ALLOWED_HOSTS:-localhost,127.0.0.1,naming-check-backend}"

if [[ -z "${TARGET_URL}" ]]; then
  log_fail "LOAD_TEST_BASE_URL is not set (create ${ENV_FILE} from .env.load.example)"
  exit 1
fi

TARGET_URL="${TARGET_URL%/}"
VERIFY_URL="${VERIFY_URL%/}"

# k6 uses Docker-internal hostname; curl from the host must hit localhost or public bind port.
target_host="$(python3 -c "from urllib.parse import urlparse; print(urlparse('${TARGET_URL}').hostname or '')")"
if [[ "${target_host}" == "naming-check-backend" && -z "${LOAD_TEST_VERIFY_URL:-}" ]]; then
  VERIFY_URL="http://127.0.0.1:8000"
fi

host="$(python3 -c "from urllib.parse import urlparse; print(urlparse('${TARGET_URL}').hostname or '')")"
if [[ -z "${host}" ]]; then
  log_fail "Cannot parse hostname from LOAD_TEST_BASE_URL=${BASE_URL}"
  exit 1
fi

IFS=',' read -r -a allowed <<< "${ALLOWED_HOSTS}"
host_allowed=0
for entry in "${allowed[@]}"; do
  entry="${entry// /}"
  if [[ "${host}" == "${entry}" ]]; then
    host_allowed=1
    break
  fi
done

if [[ "${host_allowed}" -ne 1 ]]; then
  log_fail "Host '${host}' is not in LOAD_TEST_ALLOWED_HOSTS=${ALLOWED_HOSTS}"
  log_fail "Add the host to the allowlist or fix LOAD_TEST_BASE_URL to avoid hitting the wrong environment."
  exit 1
fi

log_ok "Target host '${host}' is in allowlist"

echo "Checking application endpoints (verify=${VERIFY_URL}, k6 target=${TARGET_URL})..."

if curl -fsS --max-time 15 "${VERIFY_URL}/api/v1/health" >/dev/null; then
  log_ok "GET /api/v1/health"
else
  log_fail "GET /api/v1/health — backend unreachable or unhealthy"
fi

if curl -fsS --max-time 120 -X POST "${VERIFY_URL}/api/v1/text-similarity/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"EUROPLEX","mktu_codes":[35],"top_k":3}' >/dev/null; then
  log_ok "POST /api/v1/text-similarity/search (S1)"
else
  log_fail "POST /api/v1/text-similarity/search — text-model sidecar may be warming up"
fi

echo "Checking Docker services (optional on remote runner)..."
if command -v docker >/dev/null 2>&1; then
  for name in naming-check-backend visual-model-service text-model-service; do
    if docker ps --format '{{.Names}}' | grep -qx "${name}"; then
      log_ok "container ${name} is running"
    else
      log_warn "container ${name} not found (OK if testing remote stand from laptop)"
    fi
  done

  if docker network inspect naming-check-net >/dev/null 2>&1; then
    log_ok "docker network naming-check-net exists"
  else
    log_warn "docker network naming-check-net missing (create before k6 on-host: docker network create naming-check-net)"
  fi
else
  log_warn "docker not installed — skipping container checks"
fi

echo "Checking monitoring stack (optional)..."
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"

if curl -fsS --max-time 5 "${PROMETHEUS_URL}/-/healthy" >/dev/null 2>&1; then
  log_ok "Prometheus ${PROMETHEUS_URL}"
else
  log_warn "Prometheus not reachable at ${PROMETHEUS_URL} (start monitoring stack for metrics during load test)"
fi

if curl -fsS --max-time 5 "${GRAFANA_URL}/api/health" >/dev/null 2>&1; then
  log_ok "Grafana ${GRAFANA_URL}"
else
  log_warn "Grafana not reachable at ${GRAFANA_URL}"
fi

echo
if [[ "${failures}" -gt 0 ]]; then
  echo "Environment NOT ready (${failures} failure(s)). Fix issues above before load testing."
  exit 1
fi

echo "Environment ready for load testing."
echo "  k6 target: ${TARGET_URL}"
echo "  verify URL: ${VERIFY_URL}"
echo "  Profile: ${LOAD_TEST_PROFILE:-baseline}"
echo "  Next: bash scripts/load/run-smoke-load-test.sh"
