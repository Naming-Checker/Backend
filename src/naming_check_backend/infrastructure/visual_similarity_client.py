"""HTTP client for the CPU visual similarity sidecar (visual-model-service)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from naming_check_backend.shared.json_logging import get_request_id

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"


class VisualSimilarityUpstreamError(Exception):
    """Upstream visual-model-service returned an error or was unreachable."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def forward_logo_similarity_search(
    *,
    base_url: str,
    timeout_seconds: float,
    file_bytes: bytes,
    filename: str,
    media_type: str | None,
    top_k: int,
) -> dict[str, Any]:
    """POST multipart `file` to `{base_url}/similarity` and return parsed JSON object."""
    if not file_bytes:
        raise VisualSimilarityUpstreamError(400, "Empty image file.")

    safe_name = os.path.basename(filename) or "upload.png"
    url = f"{base_url.rstrip('/')}/similarity"
    headers: dict[str, str] = {}
    req_id = get_request_id()
    if req_id:
        headers[REQUEST_ID_HEADER] = req_id

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                url,
                params={"top_k": top_k},
                files={"file": (safe_name, file_bytes, media_type or "application/octet-stream")},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.warning(
            "visual upstream timeout",
            extra={
                "upstream_url": url,
                "upstream_status": 504,
                "filename": safe_name,
                "top_k": top_k,
            },
        )
        raise VisualSimilarityUpstreamError(504, "Visual model service request timed out.") from exc
    except httpx.RequestError as exc:
        logger.warning(
            "visual upstream unreachable",
            extra={
                "upstream_url": url,
                "upstream_status": 502,
                "filename": safe_name,
                "top_k": top_k,
            },
        )
        raise VisualSimilarityUpstreamError(
            502, f"Visual model service unreachable: {exc!s}"
        ) from exc

    if response.status_code == 200:
        payload: dict[str, Any] = response.json()
        return payload

    detail = response.text
    try:
        err_json = response.json()
        if isinstance(err_json, dict) and "detail" in err_json:
            detail_item = err_json["detail"]
            detail = str(detail_item) if not isinstance(detail_item, list) else str(detail_item)
    except ValueError:
        pass

    logger.warning(
        "visual upstream error",
        extra={
            "upstream_url": url,
            "upstream_status": response.status_code,
            "filename": safe_name,
            "top_k": top_k,
        },
    )
    if response.status_code in {400, 413, 422}:
        raise VisualSimilarityUpstreamError(response.status_code, detail)
    if response.status_code == 503:
        raise VisualSimilarityUpstreamError(503, detail)
    raise VisualSimilarityUpstreamError(
        502,
        f"Visual model service error ({response.status_code}): {detail}",
    )


async def fetch_logo_preview(
    *,
    base_url: str,
    timeout_seconds: float,
    logo_path: str,
) -> tuple[bytes, str]:
    """GET raw logo bytes from `{base_url}/asset` for preview rendering."""
    url = f"{base_url.rstrip('/')}/asset"
    headers: dict[str, str] = {}
    req_id = get_request_id()
    if req_id:
        headers[REQUEST_ID_HEADER] = req_id
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url, params={"logo_path": logo_path}, headers=headers)
    except httpx.TimeoutException as exc:
        logger.warning(
            "visual upstream timeout",
            extra={"upstream_url": url, "upstream_status": 504},
        )
        raise VisualSimilarityUpstreamError(504, "Visual model service request timed out.") from exc
    except httpx.RequestError as exc:
        logger.warning(
            "visual upstream unreachable",
            extra={"upstream_url": url, "upstream_status": 502},
        )
        raise VisualSimilarityUpstreamError(
            502, f"Visual model service unreachable: {exc!s}"
        ) from exc

    if response.status_code == 200:
        media_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, media_type

    logger.warning(
        "visual upstream error",
        extra={"upstream_url": url, "upstream_status": response.status_code},
    )
    if response.status_code in {400, 404}:
        raise VisualSimilarityUpstreamError(response.status_code, response.text)
    if response.status_code == 503:
        raise VisualSimilarityUpstreamError(503, response.text)
    raise VisualSimilarityUpstreamError(
        502,
        f"Visual model service error ({response.status_code}): {response.text}",
    )
