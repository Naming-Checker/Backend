#!/usr/bin/env bash
# Quick ELK ingest diagnostics on the test stand host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${LOGGING_DIR}/.env.elk"

if [[ -f "${ENV_FILE}" ]]; then
  ELASTIC_PASSWORD="$(grep -E '^ELASTIC_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
fi
ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"

echo "=== Containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Labels}}' | grep -E 'naming-check|visual-model|text-model|filebeat|elastic|kibana' || true

echo
echo "=== App container labels (need co.elastic.logs/enabled=true) ==="
for c in naming-check-backend visual-model-service text-model-service; do
  if docker inspect "$c" >/dev/null 2>&1; then
    docker inspect "$c" --format '{{.Name}} co.elastic.logs/enabled={{index .Config.Labels "co.elastic.logs/enabled"}}' || true
  else
    echo "$c: not running"
  fi
done

echo
echo "=== APM Server ==="
if docker ps --format '{{.Names}}' | grep -qx 'apm-server'; then
  if curl -fsS http://127.0.0.1:8200/ >/dev/null 2>&1; then
    echo "apm-server: OK"
    if docker logs apm-server --tail 200 2>&1 | grep -q 'status_code=401'; then
      echo "apm-server: WARNING — ES auth errors (401). Recreate with run-apm-server.sh entrypoint."
    fi
  else
    echo "apm-server: not responding on :8200"
  fi
else
  echo "apm-server container not running"
fi

echo
echo "=== Filebeat logs (last 40 lines) ==="
docker logs filebeat --tail 40 2>&1 || echo "filebeat container missing"

echo
echo "=== Elasticsearch log indices ==="
if [[ -n "${ELASTIC_PASSWORD}" ]]; then
  docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
    "http://localhost:9200/_cat/indices/logs-*?v&s=index" 2>/dev/null || echo "(no logs-* indices)"
  echo
  echo "Document counts by index pattern:"
  for pattern in "logs-naming-check-backend-*" "logs-visual-model-service-*" "logs-text-model-service-*" "logs-naming-check-20*"; do
    count="$(docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      "http://localhost:9200/${pattern}/_count" 2>/dev/null | grep -o '"count":[0-9]*' | cut -d: -f2 || echo "?")"
    echo "  ${pattern}: ${count}"
  done
else
  echo "Set ELASTIC_PASSWORD or .env.elk to query ES."
fi
