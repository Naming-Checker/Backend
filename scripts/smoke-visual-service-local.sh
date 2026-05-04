#!/usr/bin/env bash
# Local smoke test: build CPU image and call /health (expects mounted models dir).
#
# Usage from repo backend/:
#   bash scripts/smoke-visual-service-local.sh ../VisualModel/models
#
set -euo pipefail
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="$(cd "${1:-"$ROOT/../VisualModel/models"}" 2>/dev/null && pwd)" || MODELS_DIR=""

if [[ -z "${MODELS_DIR}" || ! -f "${MODELS_DIR}/logos_embedding.pt" ]]; then
  echo "Provide a folder with logos_embedding.pt and logos_embedding.csv (default ../VisualModel/models)." >&2
  exit 1
fi

cd "$ROOT/visual-model-service"

docker build -t visual-model-service:smoke .
docker rm -f visual-model-smoke >/dev/null 2>&1 || true
docker run -d --name visual-model-smoke \
  -p 127.0.0.1:19000:9000 \
  -v "${MODELS_DIR}:/app/models:ro" \
  visual-model-service:smoke

cleanup() {
  docker rm -f visual-model-smoke >/dev/null 2>&1 || true
}
trap cleanup EXIT

# First startup may download VGG16 weights; wait up to ~3 minutes.
ok=0
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:19000/health" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  echo "--- docker logs ---" >&2
  docker logs visual-model-smoke >&2 || true
  exit 1
fi
curl -sf "http://127.0.0.1:19000/health"

echo ""
echo "Smoke OK: GET /health"
