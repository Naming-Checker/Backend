#!/bin/sh
# Periodic index cleanup (default: every 24h). Runs maintain-indices.sh in a loop.
set -eu

INTERVAL="${MAINTENANCE_INTERVAL_SEC:-86400}"

echo "ELK maintenance loop started (interval=${INTERVAL}s)."

while true; do
  if /scripts/maintain-indices.sh; then
    echo "Maintenance run finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)."
  else
    echo "Maintenance run failed at $(date -u +%Y-%m-%dT%H:%M:%SZ)." >&2
  fi
  sleep "${INTERVAL}"
done
