#!/usr/bin/env bash
# Send a test alert to Alertmanager (verify Telegram delivery).
#
# Usage on test stand (SSH):
#   bash infra/monitoring/scripts/test-alert.sh
#
set -euo pipefail

AM_URL="${ALERTMANAGER_URL:-http://127.0.0.1:9093}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Sending TestAlert to ${AM_URL}..."

curl -fsS -X POST "${AM_URL}/api/v2/alerts" \
  -H "Content-Type: application/json" \
  -d "[{
    \"labels\": {
      \"alertname\": \"TestAlert\",
      \"severity\": \"warning\",
      \"service\": \"monitoring\"
    },
    \"annotations\": {
      \"summary\": \"Тестовый алерт naming-check monitoring\",
      \"description\": \"Если сообщение пришло в Telegram — алертинг настроен корректно.\"
    },
    \"startsAt\": \"${NOW}\"
  }]"

echo ""
echo "Test alert sent. Check Telegram within ~30s."
echo "Alertmanager UI: ${AM_URL}/#/alerts"
