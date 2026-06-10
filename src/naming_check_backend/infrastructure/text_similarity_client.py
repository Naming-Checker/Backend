"""HTTP client for text-model-service sidecar."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from naming_check_backend.shared.json_logging import get_request_id

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"


class TextSimilarityUpstreamError(Exception):
    """Upstream text-model-service returned an error or was unreachable."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def forward_text_similarity_search(
    *,
    base_url: str,
    timeout_seconds: float,
    query: str,
    mktu_codes: list[int],
    top_k: int,
) -> dict[str, Any]:
    """POST JSON payload to `{base_url}/similarity` and return parsed JSON object."""
    if not query.strip():
        raise TextSimilarityUpstreamError(400, "Query must not be empty.")

    url = f"{base_url.rstrip('/')}/similarity"
    payload = {"query": query, "mktu_codes": mktu_codes, "top_k": top_k}
    headers: dict[str, str] = {}
    req_id = get_request_id()
    if req_id:
        headers[REQUEST_ID_HEADER] = req_id
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        logger.warning(
            "text upstream timeout",
            extra={
                "upstream_url": url,
                "upstream_status": 504,
                "top_k": top_k,
                "query_length": len(query),
            },
        )
        raise TextSimilarityUpstreamError(504, "Text model service request timed out.") from exc
    except httpx.RequestError as exc:
        logger.warning(
            "text upstream unreachable",
            extra={
                "upstream_url": url,
                "upstream_status": 502,
                "top_k": top_k,
                "query_length": len(query),
            },
        )
        raise TextSimilarityUpstreamError(502, f"Text model service unreachable: {exc!s}") from exc

    if response.status_code == 200:
        parsed: dict[str, Any] = response.json()
        matches = parsed.get("matches")
        match_count = len(matches) if isinstance(matches, list) else None
        logger.info(
            "text upstream success",
            extra={
                "upstream_url": url,
                "upstream_status": 200,
                "upstream_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "query_length": len(query),
                "mktu_count": len(mktu_codes),
                "top_k": top_k,
                "match_count": match_count,
            },
        )
        return parsed

    detail = response.text
    try:
        err_json = response.json()
        if isinstance(err_json, dict) and "detail" in err_json:
            detail_item = err_json["detail"]
            detail = str(detail_item) if not isinstance(detail_item, list) else str(detail_item)
    except ValueError:
        pass

    logger.warning(
        "text upstream error",
        extra={
            "upstream_url": url,
            "upstream_status": response.status_code,
            "upstream_duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "top_k": top_k,
            "query_length": len(query),
        },
    )
    if response.status_code in {400, 422}:
        raise TextSimilarityUpstreamError(response.status_code, detail)
    if response.status_code == 503:
        raise TextSimilarityUpstreamError(503, detail)
    raise TextSimilarityUpstreamError(
        502,
        f"Text model service error ({response.status_code}): {detail}",
    )
