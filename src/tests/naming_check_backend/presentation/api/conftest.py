from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(fastapi_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(fastapi_app) as test_client:
        yield test_client
