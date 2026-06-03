from fastapi import FastAPI
from fastapi.testclient import TestClient

from naming_check_backend.presentation.middleware.request_logging import (
    REQUEST_ID_HEADER,
    RequestLoggingMiddleware,
)

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


def test_response_includes_generated_request_id() -> None:
    client = TestClient(app)
    response = client.get("/ping")
    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) > 0


def test_preserves_incoming_request_id() -> None:
    client = TestClient(app)
    custom_id = "test-req-abc-123"
    response = client.get("/ping", headers={REQUEST_ID_HEADER: custom_id})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == custom_id
