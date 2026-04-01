from fastapi.testclient import TestClient


def test_stage2_webhook_accepts_partial_results(client: TestClient) -> None:
    response = client.post(
        "/api/v1/webhooks/stage2-results",
        json={
            "correlation_id": "req-123",
            "naming": "Probimax",
            "mktu_codes": [5, 25],
            "partial": True,
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "delivery": "webhook",
        "partial": True,
        "use_case": "WebhookCallbackProcessingUseCase",
    }
