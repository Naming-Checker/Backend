from fastapi import FastAPI
from fastapi.testclient import TestClient

from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.infrastructure.ml.visual_model_adapter import VisualModelMatch


def test_registration_check_route_is_wired(client: TestClient) -> None:
    response = client.post(
        "/api/v1/registration-check",
        json={"naming": "PROBIMAX", "mktu_codes": [5, 25]},
    )

    assert response.status_code == 200
    assert response.json()["flow"] == "registration_check"
    assert response.json()["status"] == "completed"
    assert response.json()["stage2"]["delivery"] == "webhook"
    assert response.json()["meta"]["internal_result_count"] == 1


def test_text_infringement_route_is_wired(client: TestClient) -> None:
    response = client.post(
        "/api/v1/text-infringement",
        json={
            "protected_naming": "PROBIMAX",
            "suspicious_naming": "PROBI MAX",
            "mktu_codes": [5],
        },
    )

    assert response.status_code == 200
    assert response.json()["flow"] == "text_infringement"
    assert response.json()["pair_similarity"] == 94.2
    assert response.json()["stage2"]["status"] == "accepted"


def test_logo_comparison_route_is_wired(client: TestClient) -> None:
    response = client.post(
        "/api/v1/logo-comparison",
        json={
            "reference_logo": {
                "asset_ref": "logo://protected/probimax-main",
                "media_type": "image/png",
                "filename": "probimax.png",
            },
            "suspicious_logo": {
                "asset_ref": "logo://suspicious/probi-market",
                "media_type": "image/png",
                "filename": "probi-market.png",
            },
            "mktu_codes": [35],
        },
    )

    assert response.status_code == 200
    assert response.json()["flow"] == "logo_comparison"
    assert response.json()["comparison_summary"].startswith("Placeholder Stage 1 response")
    assert response.json()["stage2"]["delivery"] == "webhook"


def test_openapi_exposes_contract_schemas(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    document = response.json()
    registration_operation = document["paths"]["/api/v1/registration-check"]["post"]
    webhook_operation = document["paths"]["/api/v1/webhooks/stage2-results"]["post"]

    assert registration_operation["summary"] == "Submit registration check"
    assert webhook_operation["responses"]["202"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/Stage2WebhookResponse")
    assert "RegistrationCheckRequest" in document["components"]["schemas"]
    assert "ErrorResponse" in document["components"]["schemas"]


class _FakeVisualModelAdapter:
    def find_similar(self, image_path: str) -> list[VisualModelMatch]:
        return [
            VisualModelMatch(
                image_path="/tmp/catalog/probimax-mark.png",
                score_percent=77.3,
            )
        ]


class _MissingFileAdapter:
    def find_similar(self, image_path: str) -> list[VisualModelMatch]:
        raise FileNotFoundError(f"Logo image not found: {image_path}")


def test_logo_comparison_uses_visualmodel_adapter(fastapi_app: FastAPI, client: TestClient) -> None:
    fastapi_app.state.logo_comparison_use_case = LogoComparisonUseCase(
        visual_model_adapter=_FakeVisualModelAdapter()
    )
    response = client.post(
        "/api/v1/logo-comparison",
        json={
            "reference_logo": {
                "asset_ref": "file:///tmp/query-logo.png",
                "media_type": "image/png",
                "filename": "query-logo.png",
            },
            "suspicious_logo": {
                "asset_ref": "logo://suspicious/probi-market.png",
                "media_type": "image/png",
                "filename": "probi-market.png",
            },
            "mktu_codes": [35],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparison_summary"].startswith("Stage 1 logo comparison produced")
    assert body["internal_results"][0]["source"] == "visual_model"
    assert body["internal_results"][0]["similarity_breakdown"]["visual"] == 77.3


def test_logo_comparison_returns_400_when_reference_asset_missing(
    fastapi_app: FastAPI, client: TestClient
) -> None:
    fastapi_app.state.logo_comparison_use_case = LogoComparisonUseCase(
        visual_model_adapter=_MissingFileAdapter()
    )
    response = client.post(
        "/api/v1/logo-comparison",
        json={
            "reference_logo": {
                "asset_ref": "file:///tmp/missing-logo.png",
                "media_type": "image/png",
                "filename": "missing-logo.png",
            },
            "suspicious_logo": {
                "asset_ref": "logo://suspicious/probi-market.png",
                "media_type": "image/png",
                "filename": "probi-market.png",
            },
            "mktu_codes": [35],
        },
    )

    assert response.status_code == 400
    assert "Logo image not found" in response.json()["detail"]
