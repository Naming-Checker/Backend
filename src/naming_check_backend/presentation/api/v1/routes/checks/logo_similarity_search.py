from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from naming_check_backend.infrastructure.visual_similarity_client import (
    VisualSimilarityUpstreamError,
    forward_logo_similarity_search,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import LogoSimilaritySearchResponse
from naming_check_backend.shared.settings import settings

router = APIRouter()


@router.post(
    "/search",
    response_model=LogoSimilaritySearchResponse,
    summary="Search similar logos from an uploaded image",
    description=(
        "Accepts one logo image file, forwards it to the visual-model-service, and returns "
        "the top similar entries from the precomputed embedding index."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Visual model service error or unreachable.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Visual model service not ready (e.g. embeddings not mounted).",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "Visual model service did not respond in time.",
        },
    },
)
async def search_similar_logos(
    file: Annotated[UploadFile, File(description="Query logo image (png/jpeg/webp).")],
    top_k: Annotated[int, Query(description="Number of nearest neighbours to return.", ge=1)] = 10,
) -> LogoSimilaritySearchResponse:
    k = min(top_k, settings.visual_model_service_max_top_k)
    body = await file.read()
    try:
        raw = await forward_logo_similarity_search(
            base_url=settings.visual_model_service_base_url,
            timeout_seconds=settings.visual_model_service_timeout_seconds,
            file_bytes=body,
            filename=file.filename or "upload.png",
            media_type=file.content_type,
            top_k=k,
        )
        return LogoSimilaritySearchResponse.model_validate(raw)
    except VisualSimilarityUpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
