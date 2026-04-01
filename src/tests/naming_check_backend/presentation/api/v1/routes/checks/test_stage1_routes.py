from fastapi.testclient import TestClient


def test_registration_check_route_is_wired(client: TestClient) -> None:
    response = client.post("/api/v1/registration-check")

    assert response.status_code == 200
    assert response.json()["flow"] == "stage1_registration_check"


def test_text_infringement_route_is_wired(client: TestClient) -> None:
    response = client.post("/api/v1/text-infringement")

    assert response.status_code == 200
    assert response.json()["flow"] == "stage1_text_infringement_check"


def test_logo_comparison_route_is_wired(client: TestClient) -> None:
    response = client.post("/api/v1/logo-comparison")

    assert response.status_code == 200
    assert response.json()["flow"] == "stage1_logo_comparison"
