"""HTTP client for the CPU visual similarity sidecar (visual-model-service)."""

from __future__ import annotations

import os
from typing import Any

import httpx


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

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                url,
                params={"top_k": top_k},
                files={"file": (safe_name, file_bytes, media_type or "application/octet-stream")},
            )
    except httpx.TimeoutException as exc:
        raise VisualSimilarityUpstreamError(504, "Visual model service request timed out.") from exc
    except httpx.RequestError as exc:
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

    if response.status_code in {400, 413, 422}:
        raise VisualSimilarityUpstreamError(response.status_code, detail)
    if response.status_code == 503:
        raise VisualSimilarityUpstreamError(503, detail)
    raise VisualSimilarityUpstreamError(
        502,
        f"Visual model service error ({response.status_code}): {detail}",
    )
