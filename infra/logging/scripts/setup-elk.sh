#!/usr/bin/env bash
# Configure kibana_system password and ILM (idempotent). Safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${LOGGING_DIR}/.env.elk"

if [[ -f "${ENV_FILE}" ]]; then
  ELASTIC_PASSWORD="$(grep -E '^ELASTIC_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  KIBANA_PASSWORD="$(grep -E '^KIBANA_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
fi

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
KIBANA_PASSWORD="${KIBANA_PASSWORD:-${ELASTIC_PASSWORD:-}}"
ES_URL="${ES_URL:-http://elasticsearch:9200}"

if [[ -z "${ELASTIC_PASSWORD}" ]]; then
  echo "ELASTIC_PASSWORD is not set (expected in ${ENV_FILE} or environment)." >&2
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

echo "Setting kibana_system password..."
run_curl POST "/_security/user/kibana_system/_password" "{\"password\":\"${KIBANA_PASSWORD}\"}"

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

echo "ELK setup complete."
