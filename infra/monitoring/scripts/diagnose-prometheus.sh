#!/usr/bin/env bash
# Quick diagnostics: Prometheus scrape targets and app metrics on the test stand.
# Run on the VPS (SSH) or locally if monitoring stack is up.
set -euo pipefail

PROM_URL="${PROM_URL:-http://127.0.0.1:9090}"

echo "=== Prometheus health ==="
curl -fsS "${PROM_URL}/-/healthy" && echo " OK"

echo
echo "=== Scrape targets (up=0 means DOWN) ==="
curl -fsS "${PROM_URL}/api/v1/targets" | python3 - <<'PY'
import json, sys
data = json.load(sys.stdin)["data"]["activeTargets"]
for t in sorted(data, key=lambda x: (x.get("labels", {}).get("job", ""), x.get("scrapeUrl", ""))):
    job = t.get("labels", {}).get("job", "?")
    url = t.get("scrapeUrl", "?")
    health = t.get("health", "?")
    last = (t.get("lastError") or "").strip()
    print(f"{health:6}  {job:25}  {url}")
    if last:
        print(f"         lastError: {last}")
PY

echo
echo "=== Known app metrics in TSDB ==="
for q in 'up{job=~"naming-check-backend|visual-model-service|text-model-service"}' \
         'http_requests_total' \
         'service_health_status' \
         'probe_success'; do
  echo -n "${q}: "
  curl -fsS -G "${PROM_URL}/api/v1/query" --data-urlencode "query=${q}" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
res = r.get("data", {}).get("result", [])
print(len(res), "series" if res else "NO DATA")
PY
done

echo
echo "=== Direct /metrics from app containers (if running) ==="
for c in naming-check-backend visual-model-service text-model-service; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    port=9000
    if [[ "$c" == "naming-check-backend" ]]; then
      port=8000
    fi
    printf '%s: ' "$c"
    docker exec "$c" python -c "
import urllib.request
r = urllib.request.urlopen('http://127.0.0.1:${port}/metrics', timeout=5)
body = r.read(500).decode()
print(r.status, 'http_requests_total' in body)
" || echo "FAIL"
  fi
done

echo "=== Load test recording rules ==="
for q in 'naming_check:load_test:http_requests:rate5m' \
         'naming_check:load_test:http_requests_error_rate:percent5m' \
         'naming_check:scenario_rps:rate5m'; do
  echo -n "${q}: "
  curl -fsS -G "${PROM_URL}/api/v1/query" --data-urlencode "query=${q}" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
res = r.get("data", {}).get("result", [])
print(len(res), "series" if res else "NO DATA (need traffic + ~30s for rules)")
PY
done

echo
echo "Tips:"
echo "- Targets DOWN + lastError 404 on /metrics → deploy branch with prometheus_metrics.py not on stand yet"
echo "- Targets DOWN + 307 redirect → fixed in latest code (GET /metrics must return 200)"
echo "- up=1 but http_requests_total NO DATA → run generate-monitoring-traffic.sh"
echo "- Load test dashboard: Grafana → Naming Check → Load Testing"
echo "- Full check: bash scripts/load/verify-metrics-collection.sh"
echo "- Grafana Explore empty: pick datasource Prometheus, time range Last 30 minutes, query: up"
