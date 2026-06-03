#!/usr/bin/env bash
# Create default data view and open Discover (idempotent). Run after Kibana is healthy.
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"
ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
DATA_VIEW_ID="${DATA_VIEW_ID:-logs-naming-check}"
INDEX_PATTERN="${INDEX_PATTERN:-logs-naming-check-*}"

if [[ -z "${ELASTIC_PASSWORD}" ]]; then
  echo "ELASTIC_PASSWORD is required." >&2
  exit 1
fi

auth=(-u "elastic:${ELASTIC_PASSWORD}")
headers=(-H "kbn-xsrf: true" -H "Content-Type: application/json")

echo "Waiting for Kibana at ${KIBANA_URL}..."
for _ in $(seq 1 60); do
  if curl -fsS "${auth[@]}" "${KIBANA_URL}/api/status" | grep -q '"level":"available"'; then
    break
  fi
  sleep 5
done

if ! curl -fsS "${auth[@]}" "${KIBANA_URL}/api/status" | grep -q '"level":"available"'; then
  echo "Kibana did not become available." >&2
  exit 1
fi

echo "Creating data view ${INDEX_PATTERN}..."
status="$(curl -s -o /tmp/kibana-dv.json -w "%{http_code}" "${auth[@]}" "${headers[@]}" \
  -X POST "${KIBANA_URL}/api/data_views/data_view" \
  -d "{
    \"data_view\": {
      \"id\": \"${DATA_VIEW_ID}\",
      \"title\": \"${INDEX_PATTERN}\",
      \"name\": \"Naming Check Logs\",
      \"timeFieldName\": \"@timestamp\"
    },
    \"override\": true
  }")"

if [[ "${status}" != "200" ]] && [[ "${status}" != "409" ]]; then
  echo "Data view create failed (HTTP ${status}):" >&2
  cat /tmp/kibana-dv.json >&2 || true
  exit 1
fi

echo "Setting default data view..."
curl -fsS "${auth[@]}" "${headers[@]}" \
  -X POST "${KIBANA_URL}/api/data_views/default" \
  -d "{\"data_view_id\": \"${DATA_VIEW_ID}\"}" >/dev/null || true

echo "Creating Discover saved search (all logs)..."
curl -fsS "${auth[@]}" "${headers[@]}" \
  -X POST "${KIBANA_URL}/api/saved_objects/search/naming-check-all-logs?overwrite=true" \
  -d '{
    "attributes": {
      "title": "All Naming Check Logs",
      "description": "Application logs from backend and ML sidecars",
      "columns": ["service", "level", "message", "path", "status_code", "duration_ms", "request_id"],
      "sort": [["@timestamp", "desc"]],
      "kibanaSavedObjectMeta": {
        "searchSourceJSON": "{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[],\"indexRefName\":\"kibanaSavedObjectMeta.searchSourceJSON.index\"}"
      }
    },
    "references": [
      {
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern",
        "id": "'"${DATA_VIEW_ID}"'"
      }
    ]
  }' >/dev/null || true

echo "Kibana setup complete (Discover → Naming Check Logs)."
