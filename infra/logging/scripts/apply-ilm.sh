#!/usr/bin/env bash
# Apply 1-day ILM policy and index template for logs-naming-check-* (idempotent).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${LOGGING_DIR}/.env.elk" ]]; then
  ELASTIC_PASSWORD="$(grep -E '^ELASTIC_PASSWORD=' "${LOGGING_DIR}/.env.elk" | tail -1 | cut -d= -f2- | tr -d '"')"
fi

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"

if [[ -z "${ELASTIC_PASSWORD}" ]]; then
  echo "ELASTIC_PASSWORD is not set (expected in ${LOGGING_DIR}/.env.elk)." >&2
  exit 1
fi

run_curl() {
  local method="$1"
  local path="$2"
  local data="${3:-}"

  if docker ps --format '{{.Names}}' | grep -qx 'elasticsearch'; then
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

  local es_url="${ES_URL:-http://localhost:9200}"
  if [[ -n "${data}" ]]; then
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${es_url}${path}" \
      -H "Content-Type: application/json" \
      -d "${data}"
  else
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${es_url}${path}"
  fi
}

echo "Applying ILM policy logs-1day..."
run_curl PUT "/_ilm/policy/logs-1day" '{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_age": "1d",
            "max_primary_shard_size": "5gb"
          }
        }
      },
      "delete": {
        "min_age": "1d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}'

echo "Applying index template logs-naming-check..."
run_curl PUT "/_index_template/logs-naming-check" '{
  "index_patterns": ["logs-naming-check-*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "logs-1day"
    }
  },
  "priority": 200
}'

echo "ILM setup complete."
