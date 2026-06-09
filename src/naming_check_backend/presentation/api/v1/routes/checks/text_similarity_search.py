import logging

from fastapi import APIRouter, HTTPException, status

from naming_check_backend.infrastructure.text_similarity_client import (
    TextSimilarityUpstreamError,
    forward_text_similarity_search,
)
from naming_check_backend.presentation.api.dependencies import COMMON_ERROR_RESPONSES
from naming_check_backend.presentation.schemas import (
    TextSimilaritySearchRequest,
    TextSimilaritySearchResponse,
)
from naming_check_backend.shared.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/search",
    response_model=TextSimilaritySearchResponse,
    summary="Search similar trademark names by text",
    description=(
        "Accepts a naming query, forwards it to text-model-service, and returns "
        "the top similar entries from the precomputed text embedding index."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Text model service error or unreachable.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Text model service not ready (e.g. artifacts not mounted).",
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "description": "Text model service did not respond in time.",
        },
    },
)
async def search_similar_names(
    payload: TextSimilaritySearchRequest,
) -> TextSimilaritySearchResponse:
    k = min(payload.top_k, settings.text_model_service_max_top_k)
    try:
        raw = await forward_text_similarity_search(
            base_url=settings.text_model_service_base_url,
            timeout_seconds=settings.text_model_service_timeout_seconds,
            query=payload.query,
            mktu_codes=payload.mktu_codes,
            top_k=k,
        )
        result = TextSimilaritySearchResponse.model_validate(raw)
        logger.info(
            "text similarity search completed",
            extra={
                "query_length": len(payload.query),
                "mktu_count": len(payload.mktu_codes),
                "top_k": k,
                "match_count": len(result.matches),
            },
        )
        return result
    except TextSimilarityUpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
