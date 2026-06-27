#!/usr/bin/env bash
# Generate HTTP traffic so Grafana / Prometheus panels are not empty.
#
# Usage (local or test stand):
#   BACKEND_URL=http://127.0.0.1:8000 REQUESTS=20 bash scripts/generate-monitoring-traffic.sh
#
# On test stand:
#   BACKEND_URL=http://<TEST_STAND_HOST>:8000 REQUESTS=30 bash scripts/generate-monitoring-traffic.sh
#
# Optional logo search (needs a small png/jpeg on disk):
#   LOGO_FILE=/path/to/logo.png bash scripts/generate-monitoring-traffic.sh
#
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://45.91.236.105:8000}"
REQUESTS="${REQUESTS:-20}"
SLEEP_SEC="${SLEEP_SEC:-1}"
LOGO_FILE="${LOGO_FILE:-}"
TEXT_QUERIES="${TEXT_QUERIES:-EUROPLEX,СБЕРБАНК,МТС,ЯНДЕКС,ГАЗПРОМ}"

BACKEND_URL="${BACKEND_URL%/}"

echo "Generating monitoring traffic: backend=${BACKEND_URL}, requests=${REQUESTS}, sleep=${SLEEP_SEC}s"

IFS=',' read -r -a queries <<< "${TEXT_QUERIES}"

for i in $(seq 1 "${REQUESTS}"); do
  echo "[${i}/${REQUESTS}] health"
  curl -fsS "${BACKEND_URL}/api/v1/health" >/dev/null

  query="${queries[$((i % ${#queries[@]}))]}"
  echo "[${i}/${REQUESTS}] text similarity: ${query}"
  curl -fsS -X POST "${BACKEND_URL}/api/v1/text-similarity/search" \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"${query}\",\"mktu_codes\":[35,42],\"top_k\":5}" >/dev/null || true

  if [[ -n "${LOGO_FILE}" && -f "${LOGO_FILE}" ]]; then
    echo "[${i}/${REQUESTS}] logo similarity"
    curl -fsS -X POST "${BACKEND_URL}/api/v1/logo-similarity/search?top_k=5" \
      -F "file=@${LOGO_FILE}" >/dev/null || true
  fi

  # One deliberate 404 per loop — visible on error-rate panels, no PII.
  echo "[${i}/${REQUESTS}] probe 404"
  curl -fsS "${BACKEND_URL}/api/v1/does-not-exist" >/dev/null 2>&1 || true

  sleep "${SLEEP_SEC}"
done

echo "Done. Open Grafana → Test Stand → Services Metrics (wait ~30s for scrape)."
