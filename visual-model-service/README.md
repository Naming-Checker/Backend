# Visual model service (CPU)

Small FastAPI service that mirrors **VisualModel** combined similarity pipeline:
fine-tuned **VGG16** (`similarity.safetensors`) + cosine search over precomputed embeddings,
with optional **color-palette re-ranking**.

## Artifact layout on the server

Place these files **on the host** (not in Git — tensors are hundreds of MB):

- `logos_embedding.pt` — visual embedding matrix (fine-tuned index)
- `logos_embedding.csv` — row-aligned image paths (`data/logos/...`)
- `similarity.safetensors` — fine-tuned VGG16 weights
- `logos_embedding_colors.csv` — row-aligned color palettes (optional but recommended)

Default mount path inside the container: **`/app/models/`**.

Example on the server:

```bash
sudo mkdir -p /opt/visual-model-models
sudo cp logos_embedding.pt logos_embedding.csv \
  similarity.safetensors logos_embedding_colors.csv \
  /opt/visual-model-models/
```

## Endpoints

- `GET /health` — `200` + `{"status":"ok"}` when embeddings and model loaded; `200` + `{"status":"degraded",...}` otherwise.
- `POST /similarity?top_k=10` — multipart field `file` with a logo image; returns top similar paths and scores.

## Local run (optional)

From `backend/visual-model-service` with artifacts under `./models`:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
export EMBEDDINGS_PT_PATH=models/logos_embedding.pt
export EMBEDDINGS_CSV_PATH=models/logos_embedding.csv
export MODEL_WEIGHTS_PATH=models/similarity.safetensors
export COLORS_CSV_PATH=models/logos_embedding_colors.csv
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000
```

Environment variables map to [`app/config.py`](app/config.py):

- `EMBEDDINGS_PT_PATH`
- `EMBEDDINGS_CSV_PATH`
- `MODEL_WEIGHTS_PATH`
- `COLORS_CSV_PATH`
- `PALETTE_SIZE`, `COLOR_RERANK_POOL`, `COLOR_WORKERS`
- `APP_HOST`, `APP_PORT`
- `DEFAULT_TOP_K`, `MAX_TOP_K`
