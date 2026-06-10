import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status

from naming_check_backend.infrastructure.visual_similarity_client import (
    VisualSimilarityUpstreamError,
    fetch_logo_preview,
    forward_logo_similarity_search,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import LogoSimilaritySearchResponse
from naming_check_backend.shared.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


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
        filename = file.filename or "upload.png"
        raw = await forward_logo_similarity_search(
            base_url=settings.visual_model_service_base_url,
            timeout_seconds=settings.visual_model_service_timeout_seconds,
            file_bytes=body,
            filename=filename,
            media_type=file.content_type,
            top_k=k,
        )
        result = LogoSimilaritySearchResponse.model_validate(raw)
        logger.info(
            "logo similarity search completed",
            extra={
                "upload_filename": filename,
                "content_length": len(body),
                "top_k": k,
                "match_count": len(result.matches),
            },
        )
        return result
    except VisualSimilarityUpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/preview",
    summary="Fetch logo preview image by logo_path",
    description=(
        "Fetches a logo asset from visual-model-service using the returned `logo_path` and "
        "streams image bytes to the client."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Image bytes."},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid logo_path."},
        status.HTTP_404_NOT_FOUND: {"description": "Asset not found."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Visual model service error or unreachable."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Visual model service not ready."},
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "Visual model service timeout."},
    },
)
async def preview_logo(logo_path: Annotated[str, Query(min_length=1)]) -> Response:
    try:
        content, media_type = await fetch_logo_preview(
            base_url=settings.visual_model_service_base_url,
            timeout_seconds=settings.visual_model_service_timeout_seconds,
            logo_path=logo_path,
        )
        logger.info(
            "logo preview fetched",
            extra={
                "logo_path": logo_path,
                "content_length": len(content),
            },
        )
        return Response(content=content, media_type=media_type)
    except VisualSimilarityUpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
