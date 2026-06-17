#!/usr/bin/env bash
# Start local ELK stack for development (Elasticsearch + Kibana + Filebeat).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGGING_DIR="${ROOT}/infra/logging"
ENV_FILE="${LOGGING_DIR}/.env.elk.local"
EXAMPLE="${LOGGING_DIR}/.env.elk.example"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${EXAMPLE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} — set a strong ELASTIC_PASSWORD before use in shared environments."
fi

docker network create naming-check-net 2>/dev/null || true

docker compose -f "${LOGGING_DIR}/docker-compose.elk.yml" \
  --env-file "${ENV_FILE}" \
  --project-directory "${LOGGING_DIR}" \
  up -d

echo
echo "ELK stack is starting (elk-setup configures kibana_system + ILM + index cleanup before Kibana starts)."
echo "- Kibana UI: http://127.0.0.1:5601 (login: elastic, password ELASTIC_PASSWORD from ${ENV_FILE})"
echo "- APM traces: Kibana → Observability → APM (after app containers send data to apm-server:8200)"
echo "- Ensure app containers use network naming-check-net so Filebeat collects their logs."
echo "- Stop: docker compose -f ${LOGGING_DIR}/docker-compose.elk.yml --env-file ${ENV_FILE} --project-directory ${LOGGING_DIR} down"
