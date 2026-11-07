import os

os.environ.setdefault("JWT_SECRET", "test-secret-only-for-pytest-0123456789")

import pytest
from fastapi.testclient import TestClient

from app.core.ratelimit import get_rate_limiter
from app.main import create_app


@pytest.fixture
def client():
    get_rate_limiter.cache_clear()
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def viewer_token(client):
    response = client.post("/auth/login", json={"username": "viewer", "password": "viewer123"})
    return response.json()["access_token"]
