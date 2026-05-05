# Text model service (CPU)

Small FastAPI service that mirrors `TextModel/src/similarity.py` logic:
loads precomputed text embeddings + sidecar metadata and serves top-K cosine matches.

## Artifact layout on the server

Place these files on the host (not in Git):

- `text_embedding.pt`
- `text_embedding.csv`
- `rubert-tiny2/` (local HuggingFace snapshot for `cointegrated/rubert-tiny2`)

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
export EMBEDDINGS_PT_PATH=models/text_embedding.pt
export EMBEDDINGS_CSV_PATH=models/text_embedding.csv
export MODEL_PATH=models/rubert-tiny2
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000
```
