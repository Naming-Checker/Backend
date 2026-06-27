from fastapi.testclient import TestClient


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics", follow_redirects=False)

    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration" in body
    assert 'service="naming-check-backend"' in body


def test_health_updates_service_health_metric(client: TestClient) -> None:
    client.get("/api/v1/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert 'service_health_status{service="naming-check-backend"} 1' in response.text
