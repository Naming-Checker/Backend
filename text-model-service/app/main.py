from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.apm import configure_apm
from app.config import settings
from app.engine import TextSimilarityEngine
from app.json_logging import configure_json_logging
from app.prometheus_metrics import configure_prometheus_metrics, set_service_health
from app.request_logging import RequestLoggingMiddleware

configure_json_logging(
    service_name="text-model-service",
    env=os.environ.get("APP_ENV", "production"),
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)

_engine: TextSimilarityEngine | None = None


def _sync_load_engine() -> TextSimilarityEngine | None:
    try:
        engine = TextSimilarityEngine(
            embeddings_pt_path=settings.embeddings_pt_path,
            embeddings_csv_path=settings.embeddings_csv_path,
            model_path=settings.model_path,
            encode_batch_size=settings.encode_batch_size,
            max_length=settings.max_length,
        )
        logger.info("text similarity engine ready")
        return engine
    except FileNotFoundError as exc:
        logger.warning("text similarity engine not loaded", extra={"error": str(exc)})
        return None
    except Exception:
        logger.exception("Failed to initialize text similarity engine")
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


app = FastAPI(title="Text model service", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)


class HealthResponse(BaseModel):
    status: str
    detail: str = ""


class SimilarityRequest(BaseModel):
    query: str = Field(min_length=1)
    mktu_codes: list[int] = Field(default_factory=list)
    top_k: int | None = Field(default=None, ge=1)


class TextSimilarityMatch(BaseModel):
    name_clean: str
    name_display: str
    mark_significant: str
    certificate_link: str
    mktu_codes: list[int] = Field(default_factory=list)
    cosine_similarity: float = Field(..., ge=-1.0, le=1.0)
    similarity_percent: float


class SimilarityResponse(BaseModel):
    top_k: int
    matches: list[TextSimilarityMatch]


def engine_or_503() -> TextSimilarityEngine:
    if _engine is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Model not ready: ensure text_embedding.pt, text_embedding.csv and rubert-tiny2 "
                f"are mounted under {settings.embeddings_pt_path.rsplit('/', 1)[0]}/"
            ),
        )
    return _engine


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if _engine is None:
        set_service_health(healthy=False)
        return HealthResponse(
            status="degraded",
            detail="Embeddings or model failed to load; check mounted /app/models and logs.",
        )
    set_service_health(healthy=True)
    return HealthResponse(status="ok")


@app.post("/similarity", response_model=SimilarityResponse)
def similarity(payload: SimilarityRequest) -> SimilarityResponse:
    engine = engine_or_503()
    k = payload.top_k or settings.default_top_k
    k = max(1, min(k, settings.max_top_k))
    try:
        matches = engine.search(query=payload.query, mktu_codes=payload.mktu_codes, top_k=k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info(
        "text similarity search completed",
        extra={
            "query_length": len(payload.query),
            "mktu_count": len(payload.mktu_codes),
            "top_k": k,
            "match_count": len(matches),
        },
    )
    return SimilarityResponse(top_k=len(matches), matches=matches)


configure_apm(app, service_name="text-model-service")
configure_prometheus_metrics(app, service_name="text-model-service")
