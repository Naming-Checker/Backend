#!/usr/bin/env bash
# Verify Prometheus metrics collection for load testing (issue #74).
#
# Usage:
#   bash scripts/load/verify-metrics-collection.sh
#   PROM_URL=http://127.0.0.1:9090 bash scripts/load/verify-metrics-collection.sh
#
set -euo pipefail

PROM_URL="${PROM_URL:-http://127.0.0.1:9090}"
failures=0

log_ok() { printf '  [OK] %s\n' "$1"; }
log_warn() { printf '  [WARN] %s\n' "$1"; }
log_fail() { printf '  [FAIL] %s\n' "$1"; failures=$((failures + 1)); }

query_count() {
  local q="$1"
  curl -fsS -G "${PROM_URL}/api/v1/query" --data-urlencode "query=${q}" 2>/dev/null | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(len(r.get('data', {}).get('result', [])))
" 2>/dev/null || echo "0"
}

query_value() {
  local q="$1"
  curl -fsS -G "${PROM_URL}/api/v1/query" --data-urlencode "query=${q}" 2>/dev/null | python3 -c "
import json, sys
r = json.load(sys.stdin)
res = r.get('data', {}).get('result', [])
if not res:
    print('none')
else:
    print(res[0].get('value', ['', 'none'])[1])
" 2>/dev/null || echo "none"
}

echo "==> Verifying metrics collection for load testing"
echo "    Prometheus: ${PROM_URL}"

if curl -fsS --max-time 5 "${PROM_URL}/-/healthy" >/dev/null 2>&1; then
  log_ok "Prometheus healthy"
else
  log_fail "Prometheus not reachable at ${PROM_URL}"
  echo "Start monitoring: docker compose -f infra/monitoring/docker-compose.monitoring.yml --env-file infra/monitoring/.env.monitoring up -d"
  exit 1
fi

echo
echo "Application scrape targets:"
for job in naming-check-backend visual-model-service text-model-service; do
  up="$(query_value "up{job=\"${job}\"}")"
  if [[ "${up}" == "1" ]]; then
    log_ok "up{job=\"${job}\"} = 1"
  else
    log_fail "up{job=\"${job}\"} = ${up} (expected 1)"
  fi
done

echo
echo "Application metrics:"
for metric in http_requests_total http_request_duration_seconds_bucket service_health_status; do
  count="$(query_count "${metric}")"
  if [[ "${count}" -gt 0 ]]; then
    log_ok "${metric} (${count} series)"
  else
    log_warn "${metric} — no data yet (run traffic: bash scripts/generate-monitoring-traffic.sh)"
  fi
done

echo
echo "Recording rules (load test aggregates):"
for metric in \
  'naming_check:load_test:http_requests:rate5m' \
  'naming_check:load_test:http_requests_error_rate:percent5m' \
  'naming_check:load_test:http_request_duration_seconds:p95' \
  'naming_check:scenario_rps:rate5m'; do
  count="$(query_count "${metric}")"
  if [[ "${count}" -gt 0 ]]; then
    log_ok "${metric}"
  else
    log_warn "${metric} — no data (rules may need ~30s after traffic, or rules not loaded)"
  fi
done

rules_count="$(query_count "prometheus_rule_group_rules")"
if [[ "${rules_count}" -gt 0 ]]; then
  log_ok "Prometheus recording rules loaded (${rules_count} rules)"
else
  log_warn "Cannot confirm recording rules (reload Prometheus after deploy)"
fi

echo
echo "Infrastructure metrics:"
for q in 'up{job="node-exporter"}' 'up{job="cadvisor"}' 'node_memory_MemTotal_bytes'; do
  count="$(query_count "${q}")"
  if [[ "${count}" -gt 0 ]]; then
    log_ok "${q}"
  else
    log_fail "${q} — missing"
  fi
done

echo
echo "Database metrics:"
pg_count="$(query_count 'up{job="postgresql"}')"
ch_count="$(query_count 'up{job="clickhouse"}')"
if [[ "${pg_count}" -eq 0 && "${ch_count}" -eq 0 ]]; then
  log_ok "DB exporters not deployed (expected on MVP)"
else
  log_ok "DB exporters present (postgresql=${pg_count}, clickhouse=${ch_count})"
fi

echo
if [[ "${failures}" -gt 0 ]]; then
  echo "Metrics collection: NOT READY (${failures} failure(s))"
  echo "Run: bash infra/monitoring/scripts/diagnose-prometheus.sh"
  exit 1
fi

echo "Metrics collection: READY"
echo "Open Grafana → Naming Check → Load Testing during load test runs."
