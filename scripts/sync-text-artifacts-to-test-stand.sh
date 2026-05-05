#!/usr/bin/env bash
#
# Copies text model artifacts to the test stand server.
#
# Remote layout matches deploy workflow mount:
#   /opt/text-model-models -> text_embedding.pt, text_embedding.csv, rubert-tiny2/
#

set -euo pipefail

HOST="${TEXT_ARTIFACT_HOST:-45.91.236.105}"
REMOTE_USER="${TEXT_ARTIFACT_USER:-root}"
SSH=(ssh -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${HOST}")

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEXT_MODEL="${ROOT%/}/TextModel/models"

EMB_PT="${TEXT_MODEL}/text_embedding.pt"
EMB_CSV="${TEXT_MODEL}/text_embedding.csv"
HF_DIR="${TEXT_MODEL}/rubert-tiny2"

if [[ ! -f "$EMB_PT" || ! -f "$EMB_CSV" ]]; then
  echo "Need text_embedding.pt and text_embedding.csv in $TEXT_MODEL" >&2
  exit 1
fi
if [[ ! -d "$HF_DIR" ]]; then
  echo "Need HuggingFace snapshot directory: $HF_DIR" >&2
  exit 1
fi

echo "Ensuring directories on ${HOST} ..."
"${SSH[@]}" "mkdir -p /opt/text-model-models && chown -R root:root /opt/text-model-models 2>/dev/null || true"

RSYNC_OPTS=(-az --partial --progress --stats)
echo "Rsync embeddings ..."
rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$EMB_PT" \
  "$EMB_CSV" \
  "${REMOTE_USER}@${HOST}:/opt/text-model-models/"

echo "Rsync model snapshot (rubert-tiny2) ..."
rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$HF_DIR/" \
  "${REMOTE_USER}@${HOST}:/opt/text-model-models/rubert-tiny2/"

echo "Done."
