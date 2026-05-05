"""HTTP client for text-model-service sidecar."""

from __future__ import annotations

from typing import Any

import httpx


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
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        raise TextSimilarityUpstreamError(504, "Text model service request timed out.") from exc
    except httpx.RequestError as exc:
        raise TextSimilarityUpstreamError(502, f"Text model service unreachable: {exc!s}") from exc

    if response.status_code == 200:
        parsed: dict[str, Any] = response.json()
        return parsed

    detail = response.text
    try:
        err_json = response.json()
        if isinstance(err_json, dict) and "detail" in err_json:
            detail_item = err_json["detail"]
            detail = str(detail_item) if not isinstance(detail_item, list) else str(detail_item)
    except ValueError:
        pass

    if response.status_code in {400, 422}:
        raise TextSimilarityUpstreamError(response.status_code, detail)
    if response.status_code == 503:
        raise TextSimilarityUpstreamError(503, detail)
    raise TextSimilarityUpstreamError(
        502,
        f"Text model service error ({response.status_code}): {detail}",
    )
