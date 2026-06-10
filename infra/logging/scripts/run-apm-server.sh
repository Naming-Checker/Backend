#!/usr/bin/env sh
# Start APM Server with Elasticsearch credentials from ELASTIC_PASSWORD.
set -eu

: "${ELASTIC_PASSWORD:?ELASTIC_PASSWORD is required}"

exec apm-server -e \
  -E "apm-server.host=0.0.0.0:8200" \
  -E "output.elasticsearch.hosts=[\"http://elasticsearch:9200\"]" \
  -E "output.elasticsearch.username=elastic" \
  -E "output.elasticsearch.password=${ELASTIC_PASSWORD}" \
  -E "apm-server.auth.anonymous.enabled=true" \
  -E "apm-server.auth.anonymous.allow_agent=[\"*\"]" \
  -E "apm-server.auth.anonymous.allow_service=[\"*\"]" \
  -E "logging.level=info"
