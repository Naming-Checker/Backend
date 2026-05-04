from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from naming_check_backend.infrastructure.visual_similarity_client import (
    VisualSimilarityUpstreamError,
)


def test_logo_similarity_search_returns_upstream_payload(client: TestClient) -> None:
    payload = {
        "top_k": 2,
        "matches": [
            {
                "logo_path": "data/logos/a.jpg",
                "cosine_similarity": 0.9,
                "similarity_percent": 90.0,
            },
            {
                "logo_path": "data/logos/b.jpg",
                "cosine_similarity": 0.8,
                "similarity_percent": 80.0,
            },
        ],
    }
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.logo_similarity_search.forward_logo_similarity_search",
        new=AsyncMock(return_value=payload),
    ):
        response = client.post(
            "/api/v1/logo-similarity/search",
            files={"file": ("q.png", b"\x89PNG\r\n\x1a\n", "image/png")},
            params={"top_k": 2},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["top_k"] == 2
    assert len(data["matches"]) == 2
    assert data["matches"][0]["logo_path"] == "data/logos/a.jpg"
    assert data["matches"][0]["similarity_percent"] == 90.0


def test_logo_similarity_search_propagates_upstream_error(client: TestClient) -> None:
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.logo_similarity_search.forward_logo_similarity_search",
        new=AsyncMock(side_effect=VisualSimilarityUpstreamError(503, "degraded")),
    ):
        response = client.post(
            "/api/v1/logo-similarity/search",
            files={"file": ("q.png", b"x", "image/png")},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "degraded"
