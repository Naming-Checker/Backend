#!/usr/bin/env bash
#
# Copies embeddings + logo images used by embeddings CSV paths to the test stand server.
#
# Prerequisites:
#   - SSH works without password prompts, e.g. after:
#       ssh-copy-id -i ~/.ssh/id_ed25519.pub root@YOUR_HOST
#     (or deploy user from bootstrap-test-stand-ubuntu.sh)
#
# Env (defaults):
#   VISUAL_ARTIFACT_HOST  - default 45.91.236.105
#   VISUAL_ARTIFACT_USER  - default root (prefer non-root deploy user if configured)
#
# Remote layout matches deploy workflow mounts:
#   /opt/visual-model-models     -> logos_embedding.pt, logos_embedding.csv
#   /opt/visual-model-data       -> subtree so paths like data/logos/... exist under it
#

set -euo pipefail

HOST="${VISUAL_ARTIFACT_HOST:-45.91.236.105}"
REMOTE_USER="${VISUAL_ARTIFACT_USER:-root}"
SSH=(ssh -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${HOST}")

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VISUAL="${ROOT%/}/VisualModel"
MODELS_SRC="${VISUAL}/models"
LOGOS_SRC="${VISUAL}/data/logos"

if [[ ! -d "$MODELS_SRC" ]]; then
  echo "Missing VisualModel models dir: $MODELS_SRC" >&2
  exit 1
fi
if [[ ! -f "$MODELS_SRC/logos_embedding.pt" || ! -f "$MODELS_SRC/logos_embedding.csv" ]]; then
  echo "Need logos_embedding.pt and logos_embedding.csv in $MODELS_SRC" >&2
  exit 1
fi

if [[ ! -d "$LOGOS_SRC" ]]; then
  echo "Missing logos directory: $LOGOS_SRC (needed for CSV paths under data/logos/)" >&2
  exit 1
fi

echo "Ensuring directories on ${HOST} ..."
"${SSH[@]}" "mkdir -p /opt/visual-model-models '/opt/visual-model-data/data/logos' && chown -R root:root /opt/visual-model-models /opt/visual-model-data 2>/dev/null || true"

echo "Rsync embeddings (~386MB) ..."
# BSD rsync (macOS) has no --info=progress2; --progress works on both BSD and GNU.
RSYNC_OPTS=(-az --partial --progress --stats)

rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$MODELS_SRC/logos_embedding.pt" \
  "$MODELS_SRC/logos_embedding.csv" \
  "${REMOTE_USER}@${HOST}:/opt/visual-model-models/"

echo "Rsync logos (large, may take long) ..."
rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$LOGOS_SRC/" \
  "${REMOTE_USER}@${HOST}:/opt/visual-model-data/data/logos/"

echo "Done."
echo ""
echo "Note: embeddings CSV refers to paths like data/logos/.... If any consumer needs filesystem"
echo "access to originals, bind-mount or sync under the same prefix, e.g. mount"
echo "/opt/visual-model-data as prefix so data/logos/ resolves."
echo ""
echo "Current visual-model container mounts only embeddings from ${TEST_STAND_VISUAL_MODELS_DIR:-/opt/visual-model-models} -> /app/models."
