# Text model service (CPU)

Small FastAPI service that mirrors `TextModel/src/similarity.py` logic:
loads precomputed LaBSE embeddings + aliases sidecar and serves top-K cosine matches.

## Artifact layout on the server

Place these files on the host (not in Git):

- `embeddings.pt` — `(N, 768)` float16 L2-normalized
- `aliases.parquet` — row-aligned trademark metadata
- `class_mask.npy` — `(46, N)` bool МКТУ mask (`mask[class_id, row]`)
- `manifest.json` — build metadata / checksums
- `phonetics.parquet` — optional, not required at runtime
- `LaBSE/` — local HuggingFace snapshot for `sentence-transformers/LaBSE`
  (enough: `config.json`, `model.safetensors`, tokenizer files)

Default mount path inside container: `/app/models/`.

## Endpoints

- `GET /health` - `200` + `{\"status\":\"ok\"}` when model and embeddings are loaded; `degraded` otherwise.
- `POST /similarity` - JSON payload:

```json
{
  "query": "EUROPLEX",
  "mktu_codes": [5, 35],
  "top_k": 10
}
```

Returns top matches with text fields, certificate link, class list, and cosine scores.

## Local run (optional)

From `backend/text-model-service` with artifacts under `./models`:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
export EMBEDDINGS_PT_PATH=models/embeddings.pt
export ALIASES_PARQUET_PATH=models/aliases.parquet
export CLASS_MASK_PATH=models/class_mask.npy
export MANIFEST_PATH=models/manifest.json
export MODEL_PATH=models/LaBSE
export MAX_LENGTH=128
export MMAP_EMBEDDINGS=true
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000
```
