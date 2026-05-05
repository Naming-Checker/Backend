from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from naming_check_backend.infrastructure.text_similarity_client import TextSimilarityUpstreamError


def test_text_similarity_search_returns_upstream_payload(client: TestClient) -> None:
    payload = {
        "top_k": 2,
        "matches": [
            {
                "name_clean": "europlex",
                "name_display": "EUROPLEX",
                "mark_significant": "EUROPLEX",
                "certificate_link": "https://example.org/a",
                "mktu_codes": [5],
                "cosine_similarity": 0.91,
                "similarity_percent": 91.0,
            },
            {
                "name_clean": "euro plax",
                "name_display": "EURO PLAX",
                "mark_significant": "EURO PLAX",
                "certificate_link": "",
                "mktu_codes": [35],
                "cosine_similarity": 0.84,
                "similarity_percent": 84.0,
            },
        ],
    }
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.text_similarity_search.forward_text_similarity_search",
        new=AsyncMock(return_value=payload),
    ):
        response = client.post(
            "/api/v1/text-similarity/search",
            json={"query": "EUROPLEX", "mktu_codes": [5, 35], "top_k": 2},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["top_k"] == 2
    assert len(data["matches"]) == 2
    assert data["matches"][0]["name_display"] == "EUROPLEX"
    assert data["matches"][0]["similarity_percent"] == 91.0


def test_text_similarity_search_propagates_upstream_error(client: TestClient) -> None:
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.text_similarity_search.forward_text_similarity_search",
        new=AsyncMock(side_effect=TextSimilarityUpstreamError(503, "degraded")),
    ):
        response = client.post(
            "/api/v1/text-similarity/search",
            json={"query": "EUROPLEX", "mktu_codes": [], "top_k": 10},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "degraded"


def test_text_similarity_search_propagates_bad_gateway(client: TestClient) -> None:
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.text_similarity_search.forward_text_similarity_search",
        new=AsyncMock(side_effect=TextSimilarityUpstreamError(502, "upstream error")),
    ):
        response = client.post(
            "/api/v1/text-similarity/search",
            json={"query": "EUROPLEX", "mktu_codes": [], "top_k": 10},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "upstream error"


def test_text_similarity_search_propagates_timeout(client: TestClient) -> None:
    with patch(
        "naming_check_backend.presentation.api.v1.routes.checks.text_similarity_search.forward_text_similarity_search",
        new=AsyncMock(side_effect=TextSimilarityUpstreamError(504, "timed out")),
    ):
        response = client.post(
            "/api/v1/text-similarity/search",
            json={"query": "EUROPLEX", "mktu_codes": [], "top_k": 10},
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "timed out"
