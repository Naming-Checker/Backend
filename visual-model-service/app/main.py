from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.engine import SimilarityEngine
from app.json_logging import configure_json_logging
from app.request_logging import RequestLoggingMiddleware

configure_json_logging(
    service_name="visual-model-service",
    env=os.environ.get("APP_ENV", "production"),
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)

_engine: SimilarityEngine | None = None


def _sync_load_engine() -> SimilarityEngine | None:
    """Blocking load; run via asyncio.to_thread so Uvicorn binds and /health responds while loading."""
    try:
        eng = SimilarityEngine(
            embeddings_pt_path=settings.embeddings_pt_path,
            embeddings_csv_path=settings.embeddings_csv_path,
        )
        logger.info("similarity engine ready")
        return eng
    except FileNotFoundError as exc:
        logger.warning("similarity engine not loaded", extra={"error": str(exc)})
        return None
    except Exception:
        logger.exception("Failed to initialize similarity engine")
        return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _engine

    async def load_task() -> None:
        global _engine
        _engine = await asyncio.to_thread(_sync_load_engine)

    task = asyncio.create_task(load_task())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        _engine = None


app = FastAPI(title="Visual model service", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
_assets_root = Path(settings.assets_root).resolve()


class HealthResponse(BaseModel):
    status: str
    detail: str = ""


class MatchItem(BaseModel):
    logo_path: str
    cosine_similarity: float = Field(..., description="Cosine similarity in [-1, 1].")
    similarity_percent: float = Field(..., description="cosine_similarity * 100.")


class SimilarityResponse(BaseModel):
    top_k: int
    matches: list[MatchItem]


def engine_or_503() -> SimilarityEngine:
    if _engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Model not ready: ensure logos_embedding.pt and logos_embedding.csv are mounted "
                f"under {settings.embeddings_pt_path.rsplit('/', 1)[0]}/"
            ),
        )
    return _engine


def resolve_logo_asset_path(logo_path: str) -> Path:
    normalized = logo_path.strip().replace("\\", "/")
    if not normalized:
        raise HTTPException(status_code=400, detail="logo_path is required.")
    candidate = (_assets_root / normalized).resolve()
    if not candidate.is_relative_to(_assets_root):
        raise HTTPException(status_code=400, detail="logo_path points outside assets_root.")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Logo asset not found.")
    return candidate


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if _engine is None:
        return HealthResponse(
            status="degraded",
            detail="Embeddings or model failed to load; check mounted /app/models and logs.",
        )
    return HealthResponse(status="ok")


@app.post("/similarity", response_model=SimilarityResponse)
def similarity(
    file: Annotated[UploadFile, File(description="Query logo image (png/jpeg/webp).")],
    top_k: Annotated[int, Query(ge=1)] = 10,
) -> SimilarityResponse:
    eng = engine_or_503()
    k = max(1, min(top_k, settings.max_top_k))

    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", maxsplit=1)[-1].lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        suffix = ".png"

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="query-logo-", suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        rows = eng.top_k_similar(tmp_path, k=k)
        matches = [
            MatchItem(logo_path=p, cosine_similarity=cos, similarity_percent=pct) for p, cos, pct in rows
        ]
        logger.info(
            "logo similarity search completed",
            extra={
                "content_length": len(data),
                "top_k": k,
                "match_count": len(matches),
            },
        )
        return SimilarityResponse(top_k=len(matches), matches=matches)
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("could not delete temp file", extra={"temp_path": tmp_path})


@app.get("/asset")
def get_logo_asset(
    logo_path: Annotated[str, Query(description="Relative path from assets_root, e.g. data/logos/a.jpg")],
) -> FileResponse:
    path = resolve_logo_asset_path(logo_path)
    logger.info("logo asset served", extra={"logo_path": logo_path})
    return FileResponse(path)
