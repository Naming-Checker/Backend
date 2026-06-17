#!/bin/sh
# Configure kibana_system password, ILM, and index templates (idempotent). Safe to re-run.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${LOGGING_DIR}/.env.elk"
if [ -z "${TEMPLATE_DIR:-}" ]; then
  TEMPLATE_DIR="${LOGGING_DIR}/templates"
fi
TEMPLATE_FILE="${TEMPLATE_DIR}/logs-index-template.json"

if [[ -f "${ENV_FILE}" ]]; then
  ELASTIC_PASSWORD="$(grep -E '^ELASTIC_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  KIBANA_PASSWORD="$(grep -E '^KIBANA_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  LOG_RETENTION_DAYS="$(grep -E '^LOG_RETENTION_DAYS=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  APM_RETENTION_DAYS="$(grep -E '^APM_RETENTION_DAYS=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
fi

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
KIBANA_PASSWORD="${KIBANA_PASSWORD:-${ELASTIC_PASSWORD:-}}"
ES_URL="${ES_URL:-http://elasticsearch:9200}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-1}"
APM_RETENTION_DAYS="${APM_RETENTION_DAYS:-1}"

if [[ -z "${ELASTIC_PASSWORD}" ]]; then
  echo "ELASTIC_PASSWORD is not set (expected in ${ENV_FILE} or environment)." >&2
  exit 1
fi

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "Index template file not found: ${TEMPLATE_FILE}" >&2
  exit 1
fi

run_curl() {
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if [[ -n "${USE_DOCKER_EXEC:-}" ]] && docker ps --format '{{.Names}}' | grep -qx 'elasticsearch'; then
    if [[ -n "${data}" ]]; then
      docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
        -X "${method}" "http://localhost:9200${path}" \
        -H "Content-Type: application/json" \
        -d "${data}"
    else
      docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
        -X "${method}" "http://localhost:9200${path}"
    fi
    return
  fi

  if [[ -n "${data}" ]]; then
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${ES_URL}${path}" \
      -H "Content-Type: application/json" \
      -d "${data}"
  else
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${ES_URL}${path}"
  fi
}

run_curl_file() {
  local method="$1"
  local path="$2"
  local file="$3"

  if [[ -n "${USE_DOCKER_EXEC:-}" ]] && docker ps --format '{{.Names}}' | grep -qx 'elasticsearch'; then
    docker exec -i elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "http://localhost:9200${path}" \
      -H "Content-Type: application/json" \
      -d @"-" <"${file}"
    return
  fi

  curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
    -X "${method}" "${ES_URL}${path}" \
    -H "Content-Type: application/json" \
    -d @"${file}"
}

echo "Setting kibana_system password..."
run_curl POST "/_security/user/kibana_system/_password" "{\"password\":\"${KIBANA_PASSWORD}\"}"

echo "Applying ILM policy logs-1day (delete after ${LOG_RETENTION_DAYS}d)..."
run_curl PUT "/_ilm/policy/logs-1day" "{
  \"policy\": {
    \"phases\": {
      \"hot\": {
        \"min_age\": \"0ms\",
        \"actions\": {}
      },
      \"delete\": {
        \"min_age\": \"${LOG_RETENTION_DAYS}d\",
        \"actions\": {
          \"delete\": {}
        }
      }
    }
  }
}"

echo "Removing obsolete index template logs-naming-check (replaced by logs-app)..."
run_curl DELETE "/_index_template/logs-naming-check" || true
run_curl DELETE "/_index_template/logs" || true

echo "Applying index template logs-app (per-service Filebeat indices)..."
run_curl_file PUT "/_index_template/logs-app" "${TEMPLATE_FILE}"

echo "Applying legacy index template for old daily indices (logs-naming-check-YYYY.MM.DD)..."
run_curl PUT "/_index_template/logs-naming-check-legacy" '{
  "index_patterns": ["logs-naming-check-20*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "logs-1day",
      "index.number_of_shards": 1,
      "index.number_of_replicas": 0
    }
  },
  "priority": 50
}'

echo "Applying ILM policy apm-1day (delete after ${APM_RETENTION_DAYS}d)..."
run_curl PUT "/_ilm/policy/apm-1day" "{
  \"policy\": {
    \"phases\": {
      \"hot\": {
        \"min_age\": \"0ms\",
        \"actions\": {}
      },
      \"delete\": {
        \"min_age\": \"${APM_RETENTION_DAYS}d\",
        \"actions\": {
          \"delete\": {}
        }
      }
    }
  }
}"

for pattern in traces-apm metrics-apm logs-apm; do
  echo "Applying index template ${pattern}-1day..."
  run_curl PUT "/_index_template/${pattern}-1day" "{
    \"index_patterns\": [\"${pattern}-*\"],
    \"template\": {
      \"settings\": {
        \"index.lifecycle.name\": \"apm-1day\"
      }
    },
    \"priority\": 150
  }"
done

echo "Running index maintenance (attach ILM + purge stale indices)..."
if [ -x "${SCRIPT_DIR}/maintain-indices.sh" ]; then
  ELASTIC_PASSWORD="${ELASTIC_PASSWORD}" \
  ES_URL="${ES_URL}" \
  LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS}" \
  APM_RETENTION_DAYS="${APM_RETENTION_DAYS}" \
  "${SCRIPT_DIR}/maintain-indices.sh"
else
  echo "maintain-indices.sh not found, skipping maintenance step." >&2
fi

echo "ELK setup complete."
