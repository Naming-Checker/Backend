#!/usr/bin/env bash
#
# Copies text model artifacts to the test stand server.
#
# Remote layout matches deploy workflow mount:
#   /opt/text-model-models ->
#     embeddings.f16.npy (+ .meta.json)  OR embeddings.pt
#     aliases.parquet, class_mask.npy, manifest.json
#     phonetics.parquet (optional)
#     LaBSE/  (config + model.safetensors + tokenizer; no onnx/flax/tf)
#
# Usage:
#   TEXT_ARTIFACTS_DIR=~/Downloads bash scripts/sync-text-artifacts-to-test-stand.sh
#   TEXT_ARTIFACTS_DIR=../TextModel/models bash scripts/sync-text-artifacts-to-test-stand.sh
#

set -euo pipefail

HOST="${TEXT_ARTIFACT_HOST:-45.91.236.105}"
REMOTE_USER="${TEXT_ARTIFACT_USER:-root}"
SSH=(ssh -o StrictHostKeyChecking=accept-new "${REMOTE_USER}@${HOST}")

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACTS_DIR="${TEXT_ARTIFACTS_DIR:-${ROOT%/}/TextModel/models}"

ALIASES="${ARTIFACTS_DIR}/aliases.parquet"
CLASS_MASK="${ARTIFACTS_DIR}/class_mask.npy"
MANIFEST="${ARTIFACTS_DIR}/manifest.json"
HF_DIR="${ARTIFACTS_DIR}/LaBSE"
EMB_NPY="${ARTIFACTS_DIR}/embeddings.f16.npy"
EMB_META="${ARTIFACTS_DIR}/embeddings.f16.npy.meta.json"
EMB_PT="${ARTIFACTS_DIR}/embeddings.pt"

for f in "$ALIASES" "$CLASS_MASK" "$MANIFEST"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing artifact: $f" >&2
    exit 1
  fi
done
if [[ ! -f "$EMB_NPY" && ! -f "$EMB_PT" ]]; then
  echo "Need embeddings.f16.npy (preferred) or embeddings.pt in $ARTIFACTS_DIR" >&2
  exit 1
fi
if [[ ! -d "$HF_DIR" ]]; then
  echo "Need LaBSE snapshot directory: $HF_DIR" >&2
  echo "Hint: huggingface-cli download sentence-transformers/LaBSE --local-dir TextModel/models/LaBSE" >&2
  exit 1
fi

echo "Ensuring directories on ${HOST} ..."
"${SSH[@]}" "mkdir -p /opt/text-model-models && chown -R root:root /opt/text-model-models 2>/dev/null || true"

RSYNC_OPTS=(-az --partial --progress --stats)
echo "Rsync index artifacts ..."
rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$ALIASES" \
  "$CLASS_MASK" \
  "$MANIFEST" \
  "${REMOTE_USER}@${HOST}:/opt/text-model-models/"

if [[ -f "$EMB_NPY" && -f "$EMB_META" ]]; then
  echo "Rsync float16 memmap embeddings ..."
  rsync "${RSYNC_OPTS[@]}" \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    "$EMB_NPY" \
    "$EMB_META" \
    "${REMOTE_USER}@${HOST}:/opt/text-model-models/"
elif [[ -f "$EMB_PT" ]]; then
  echo "Rsync embeddings.pt (will be converted to memmap on first start) ..."
  rsync "${RSYNC_OPTS[@]}" \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    "$EMB_PT" \
    "${REMOTE_USER}@${HOST}:/opt/text-model-models/"
fi

if [[ -f "${ARTIFACTS_DIR}/phonetics.parquet" ]]; then
  echo "Rsync phonetics.parquet ..."
  rsync "${RSYNC_OPTS[@]}" \
    -e "ssh -o StrictHostKeyChecking=accept-new" \
    "${ARTIFACTS_DIR}/phonetics.parquet" \
    "${REMOTE_USER}@${HOST}:/opt/text-model-models/"
fi

echo "Rsync LaBSE (weights + tokenizer only) ..."
rsync "${RSYNC_OPTS[@]}" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  --exclude '.cache' \
  --exclude 'onnx' \
  --exclude 'flax_model.msgpack' \
  --exclude 'pytorch_model.bin' \
  --exclude 'tf_model.h5' \
  "$HF_DIR/" \
  "${REMOTE_USER}@${HOST}:/opt/text-model-models/LaBSE/"

echo "Done."
