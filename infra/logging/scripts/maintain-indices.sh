#!/bin/sh
# Attach ILM to existing indices and delete data older than retention (idempotent).
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGGING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${LOGGING_DIR}/.env.elk"

if [ -f "${ENV_FILE}" ]; then
  ELASTIC_PASSWORD="$(grep -E '^ELASTIC_PASSWORD=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  LOG_RETENTION_DAYS="$(grep -E '^LOG_RETENTION_DAYS=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
  APM_RETENTION_DAYS="$(grep -E '^APM_RETENTION_DAYS=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | tr -d '"')"
fi

ELASTIC_PASSWORD="${ELASTIC_PASSWORD:-}"
ES_URL="${ES_URL:-http://elasticsearch:9200}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-1}"
APM_RETENTION_DAYS="${APM_RETENTION_DAYS:-1}"
LOGS_ILM_POLICY="${LOGS_ILM_POLICY:-logs-1day}"
APM_ILM_POLICY="${APM_ILM_POLICY:-apm-1day}"

if [ -z "${ELASTIC_PASSWORD}" ]; then
  echo "ELASTIC_PASSWORD is not set (expected in ${ENV_FILE} or environment)." >&2
  exit 1
fi

run_curl() {
  method="$1"
  path="$2"
  data="${3:-}"

  if [ -n "${USE_DOCKER_EXEC:-}" ] && docker ps --format '{{.Names}}' | grep -qx 'elasticsearch'; then
    if [ -n "${data}" ]; then
      docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
        -X "${method}" "http://localhost:9200${path}" \
        -H "Content-Type: application/json" \
        -d "${data}" || return 1
    else
      docker exec elasticsearch curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
        -X "${method}" "http://localhost:9200${path}" || return 1
    fi
    return 0
  fi

  if [ -n "${data}" ]; then
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${ES_URL}${path}" \
      -H "Content-Type: application/json" \
      -d "${data}" || return 1
  else
    curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
      -X "${method}" "${ES_URL}${path}" || return 1
  fi
}

run_curl_allow_404() {
  run_curl "$@" || true
}

attach_ilm() {
  pattern="$1"
  policy="$2"

  echo "Attaching ILM policy ${policy} to indices matching ${pattern}..."
  run_curl_allow_404 PUT "/${pattern}/_settings" "{\"index\":{\"lifecycle\":{\"name\":\"${policy}\"}}}"
}

purge_indices_older_than_days() {
  pattern="$1"
  retention_days="$2"

  echo "Purging indices matching ${pattern} older than ${retention_days} day(s)..."
  cutoff_ms=$(( $(date +%s) * 1000 - retention_days * 86400000 ))
  deleted=0
  lines=""

  lines="$(run_curl GET "/_cat/indices/${pattern}?h=index,creation.date" 2>/dev/null || true)"
  if [ -z "${lines}" ]; then
    echo "No indices matched ${pattern}."
    return 0
  fi

  echo "${lines}" | while read -r index created_ms; do
    [ -z "${index}" ] && continue
    [ "${index}" = "index" ] && continue
    [ -z "${created_ms}" ] && continue
    case "${created_ms}" in
      *[!0-9]*) continue ;;
    esac
    if [ "${created_ms}" -lt "${cutoff_ms}" ]; then
      echo "Deleting stale index ${index} (created ${created_ms})..."
      run_curl_allow_404 DELETE "/${index}"
      deleted=$((deleted + 1))
    fi
  done

  echo "Purge pass complete for ${pattern}."
}

ensure_ilm_started() {
  echo "Ensuring ILM is running..."
  run_curl_allow_404 POST "/_ilm/start"
}

retry_failed_ilm() {
  echo "Retrying ILM for log indices in ERROR state..."
  lines=""

  lines="$(run_curl GET "/logs-*/_ilm/explain?only_errors=true&h=index" 2>/dev/null || true)"
  if [ -z "${lines}" ]; then
    return 0
  fi

  echo "${lines}" | while read -r index _rest; do
    [ -z "${index}" ] && continue
    [ "${index}" = "index" ] && continue
    echo "Retrying ILM for ${index}..."
    run_curl_allow_404 POST "/${index}/_ilm/retry"
  done
}

echo "=== ELK index maintenance (logs retention=${LOG_RETENTION_DAYS}d, apm retention=${APM_RETENTION_DAYS}d) ==="

ensure_ilm_started

attach_ilm "logs-*" "${LOGS_ILM_POLICY}"
attach_ilm "logs-naming-check-20*" "${LOGS_ILM_POLICY}"
attach_ilm "traces-apm-*" "${APM_ILM_POLICY}"
attach_ilm "metrics-apm-*" "${APM_ILM_POLICY}"
attach_ilm "logs-apm-*" "${APM_ILM_POLICY}"

purge_indices_older_than_days "logs-*" "${LOG_RETENTION_DAYS}"
purge_indices_older_than_days "logs-naming-check-20*" "${LOG_RETENTION_DAYS}"
purge_indices_older_than_days "traces-apm-*" "${APM_RETENTION_DAYS}"
purge_indices_older_than_days "metrics-apm-*" "${APM_RETENTION_DAYS}"
purge_indices_older_than_days "logs-apm-*" "${APM_RETENTION_DAYS}"

retry_failed_ilm

echo "Index maintenance complete."
