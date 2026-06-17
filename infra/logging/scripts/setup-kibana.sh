#!/usr/bin/env bash
# Create data views, saved searches, and default Discover (idempotent). Run after Kibana is healthy.
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"
ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"

if [[ -z "${ELASTIC_PASSWORD}" ]]; then
  echo "ELASTIC_PASSWORD is required." >&2
  exit 1
fi

auth=(-u "elastic:${ELASTIC_PASSWORD}")
headers=(-H "kbn-xsrf: true" -H "Content-Type: application/json")

create_data_view() {
  local id="$1"
  local title="$2"
  local name="$3"

  echo "Creating data view ${title} (${name})..."
  local status
  status="$(curl -s -o /tmp/kibana-dv-"${id}".json -w "%{http_code}" "${auth[@]}" "${headers[@]}" \
    -X POST "${KIBANA_URL}/api/data_views/data_view" \
    -d "{
      \"data_view\": {
        \"id\": \"${id}\",
        \"title\": \"${title}\",
        \"name\": \"${name}\",
        \"timeFieldName\": \"@timestamp\"
      },
      \"override\": true
    }")"

  if [[ "${status}" != "200" ]] && [[ "${status}" != "409" ]]; then
    echo "Data view create failed for ${id} (HTTP ${status}):" >&2
    cat "/tmp/kibana-dv-${id}.json" >&2 || true
    return 1
  fi
}

create_saved_search() {
  local object_id="$1"
  local title="$2"
  local description="$3"
  local data_view_id="$4"
  local query="$5"
  local columns_json="$6"

  echo "Creating saved search: ${title}..."
  curl -fsS "${auth[@]}" "${headers[@]}" \
    -X POST "${KIBANA_URL}/api/saved_objects/search/${object_id}?overwrite=true" \
    -d "{
      \"attributes\": {
        \"title\": \"${title}\",
        \"description\": \"${description}\",
        \"columns\": ${columns_json},
        \"sort\": [[\"@timestamp\", \"desc\"]],
        \"kibanaSavedObjectMeta\": {
          \"searchSourceJSON\": \"{\\\"query\\\":{\\\"query\\\":\\\"${query}\\\",\\\"language\\\":\\\"kuery\\\"},\\\"filter\\\":[],\\\"indexRefName\\\":\\\"kibanaSavedObjectMeta.searchSourceJSON.index\\\"}\"
        }
      },
      \"references\": [
        {
          \"name\": \"kibanaSavedObjectMeta.searchSourceJSON.index\",
          \"type\": \"index-pattern\",
          \"id\": \"${data_view_id}\"
        }
      ]
    }" >/dev/null || true
}

echo "Waiting for Kibana at ${KIBANA_URL}..."
ready=0
for _ in $(seq 1 60); do
  if curl -fsS "${auth[@]}" "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; then
    ready=1
    break
  fi
  sleep 5
done

if [[ "${ready}" != 1 ]]; then
  echo "Kibana did not become available." >&2
  exit 1
fi

COLUMNS='["service", "level", "message", "path", "status_code", "duration_ms", "request_id", "trace.id"]'

create_data_view "logs-all" "logs-*" "All Application Logs"
create_data_view "logs-backend" "logs-naming-check-backend-*" "Backend Logs"
create_data_view "logs-visual" "logs-visual-model-service-*" "Visual Model Logs"
create_data_view "logs-text" "logs-text-model-service-*" "Text Model Logs"

echo "Setting default data view to logs-all..."
curl -fsS "${auth[@]}" "${headers[@]}" \
  -X POST "${KIBANA_URL}/api/data_views/default" \
  -d '{"data_view_id": "logs-all"}' >/dev/null || true

create_saved_search \
  "naming-check-all-logs" \
  "All Application Logs" \
  "All services (backend + ML sidecars)" \
  "logs-all" \
  "" \
  "${COLUMNS}"

create_saved_search \
  "naming-check-errors" \
  "Errors and Warnings" \
  "level ERROR or WARNING" \
  "logs-all" \
  "level: (ERROR or WARNING)" \
  "${COLUMNS}"

create_saved_search \
  "naming-check-http-5xx" \
  "HTTP 5xx" \
  "Requests with status_code >= 500" \
  "logs-all" \
  "status_code >= 500" \
  "${COLUMNS}"

create_saved_search \
  "naming-check-slow-requests" \
  "Slow Requests (>3s)" \
  "HTTP requests slower than 3000 ms" \
  "logs-all" \
  "duration_ms > 3000" \
  "${COLUMNS}"

create_saved_search \
  "naming-check-backend-only" \
  "Backend Only" \
  "naming-check-backend service" \
  "logs-backend" \
  "service: naming-check-backend" \
  "${COLUMNS}"

echo "Kibana setup complete (Discover → All Application Logs, saved searches installed)."
