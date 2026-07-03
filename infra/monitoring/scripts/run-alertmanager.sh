#!/bin/sh
# Generate Alertmanager config from env and start the process.
set -eu

OUT=/tmp/alertmanager.yml
TG_TOKEN="${ALERTMANAGER_TELEGRAM_BOT_TOKEN:-}"
TG_CHAT="${ALERTMANAGER_TELEGRAM_CHAT_ID:-}"

cat >"$OUT" <<'EOF'
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'service', 'job', 'instance']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: notifications
  routes:
    - matchers:
        - alertname="TestAlert"
      receiver: notifications
      group_wait: 5s
      repeat_interval: 2m

inhibit_rules:
  - source_matchers:
      - severity="critical"
    target_matchers:
      - severity="warning"
    equal: ['alertname', 'service', 'instance']

receivers:
  - name: notifications
EOF

if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ]; then
  cat >>"$OUT" <<EOF
    telegram_configs:
      - bot_token: '${TG_TOKEN}'
        chat_id: ${TG_CHAT}
        parse_mode: HTML
        message: |
          {{ range .Alerts }}
          <b>{{ .Labels.alertname }}</b> [{{ .Labels.severity }}]
          {{ .Annotations.summary }}
          {{ .Annotations.description }}
          {{ end }}
EOF
  echo "Alertmanager: Telegram notifications enabled (chat_id=${TG_CHAT})."
else
  echo "WARNING: ALERTMANAGER_TELEGRAM_BOT_TOKEN or ALERTMANAGER_TELEGRAM_CHAT_ID not set." >&2
  echo "WARNING: Alerts will appear in Alertmanager UI only (http://127.0.0.1:9093)." >&2
fi

exec /bin/alertmanager \
  --config.file="$OUT" \
  --storage.path=/alertmanager \
  --web.listen-address=:9093
