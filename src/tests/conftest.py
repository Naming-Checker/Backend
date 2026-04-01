from collections.abc import Iterator

import pytest
from fastapi import FastAPI

from naming_check_backend.main import app


@pytest.fixture
def fastapi_app() -> Iterator[FastAPI]:
    yield app
