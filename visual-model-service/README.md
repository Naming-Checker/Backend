# Visual model service (CPU)

Small FastAPI service that mirrors **VisualModel** `similarity.py` logic (upstream project): loads **VGG16 (ImageNet)** and searches against precomputed embeddings.

## Artifact layout on the server

Place these files **on the host** (not in Git — the `.pt` is ~380MB):

- `logos_embedding.pt`
- `logos_embedding.csv`

Default mount path inside the container: **`/app/models/`**.

Example on the server:

```bash
sudo mkdir -p /opt/visual-model-service/models
sudo cp logos_embedding.pt logos_embedding.csv /opt/visual-model-service/models/
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
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000
```

Environment variables map to [`app/config.py`](app/config.py):

- `EMBEDDINGS_PT_PATH`
- `EMBEDDINGS_CSV_PATH`
- `APP_HOST`, `APP_PORT`
- `DEFAULT_TOP_K`, `MAX_TOP_K`
