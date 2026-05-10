#!/usr/bin/env bash
# Local smoke test: build image and call /health + /similarity.
#
# Usage from repo backend/:
#   bash scripts/smoke-text-service-local.sh ../TextModel/models
#
set -euo pipefail
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="$(cd "${1:-"$ROOT/../TextModel/models"}" 2>/dev/null && pwd)" || MODELS_DIR=""

if [[ -z "${MODELS_DIR}" || ! -f "${MODELS_DIR}/text_embedding.pt" || ! -f "${MODELS_DIR}/text_embedding.csv" ]]; then
  echo "Provide a folder with text_embedding.pt and text_embedding.csv (default ../TextModel/models)." >&2
  exit 1
fi
if [[ ! -d "${MODELS_DIR}/rubert-tiny2" ]]; then
  echo "Provide rubert-tiny2 snapshot under ${MODELS_DIR}/rubert-tiny2." >&2
  exit 1
fi

cd "$ROOT/text-model-service"

docker build -t text-model-service:smoke .
docker rm -f text-model-smoke >/dev/null 2>&1 || true
docker run -d --name text-model-smoke \
  -p 127.0.0.1:19100:9000 \
  -v "${MODELS_DIR}:/app/models:ro" \
  text-model-service:smoke

cleanup() {
  docker rm -f text-model-smoke >/dev/null 2>&1 || true
}
trap cleanup EXIT

ok=0
for _ in $(seq 1 80); do
  if curl -sf "http://127.0.0.1:19100/health" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  echo "--- docker logs ---" >&2
  docker logs text-model-smoke >&2 || true
  exit 1
fi

curl -sf -X POST "http://127.0.0.1:19100/similarity" \
  -H "Content-Type: application/json" \
  -d '{"query":"EUROPLEX","top_k":3,"mktu_codes":[]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'matches' in d and 'top_k' in d; print(json.dumps({'top_k': d['top_k'], 'sample_match': (d['matches'][0] if d['matches'] else None)}, ensure_ascii=False))"

echo ""
echo "Smoke OK: GET /health and POST /similarity"
