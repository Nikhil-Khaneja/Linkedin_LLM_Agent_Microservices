import os

import pytest
from fastapi.testclient import TestClient

os.environ["MYSQL_URL"] = "sqlite:///./test_auth.db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/1"

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)