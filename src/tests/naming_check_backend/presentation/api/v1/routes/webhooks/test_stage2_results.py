from fastapi.testclient import TestClient


def test_stage2_webhook_accepts_partial_results(client: TestClient) -> None:
    response = client.post(
        "/api/v1/webhooks/stage2-results",
        json={
            "correlation_id": "req-123",
            "flow": "registration_check",
            "status": "partial",
            "naming": "Probimax",
            "mktu_codes": [5, 25],
            "partial": True,
            "matches": [
                {
                    "candidate_id": "ext-001",
                    "candidate_name": "Probimax Mobile",
                    "source": "google_play",
                    "mktu_codes": [9],
                    "similarity": 81.0,
                }
            ],
            "source_batch": ["google_play"],
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "delivery": "webhook",
        "processing_status": "accepted",
        "correlation_id": "req-123",
        "partial": True,
        "use_case": "WebhookCallbackProcessingUseCase",
    }
