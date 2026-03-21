from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.app import create_app
from app.config import Settings
from app.db import init_db
from app.services.identity_service import FaceAnalysis


@pytest.fixture
def client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        auto_create_tables=True,
        rate_limit_enabled=False,
        environment="test",
        debug=False,
        secret_key="test-secret",
    )
    app = create_app(settings)
    init_db(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_factory(client: TestClient):
    def _create(email: str, name: str, password: str = "secret123"):
        response = client.post(
            "/auth/register",
            json={"email": email, "password": password, "name": name, "mode": "free", "interests": ["music", "coffee"]},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture
def auth_headers():
    def _headers(token: str):
        return {"Authorization": f"Bearer {token}"}

    return _headers


class FakeFaceAnalyzer:
    def available(self) -> bool:
        return True

    def analyze(self, file_bytes: bytes) -> FaceAnalysis:
        text = file_bytes.decode("utf-8", errors="ignore")
        if "NO_FACE" in text:
            return FaceAnalysis([], 0, 0.6, 320, 320, ["no_face"], "review_required")
        if "MULTIPLE_FACES" in text:
            return FaceAnalysis([], 2, 0.7, 320, 320, ["multiple_faces"], "review_required")
        if "LOW_QUALITY" in text:
            return FaceAnalysis([], 1, 0.1, 120, 120, ["low_quality"], "review_required")
        if "MATCH_A" in text:
            embedding = [0.1, 0.2, 0.3, 0.4]
        elif "MATCH_B" in text:
            embedding = [0.1, 0.2, 0.3, 0.39]
        elif "MATCH_C" in text:
            embedding = [0.09, 0.19, 0.31, 0.41]
        else:
            embedding = [0.4, 0.3, 0.2, 0.1]
        return FaceAnalysis(embedding, 1, 0.9, 320, 320, [], "passed", 0.95)


@pytest.fixture
def identity_enabled_client(tmp_path: Path):
    db_path = tmp_path / "identity.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        auto_create_tables=True,
        rate_limit_enabled=False,
        environment="test",
        debug=False,
        secret_key="test-secret",
        feature_identity_enabled=True,
    )
    app = create_app(settings)
    app.state.identity_service.analyzer = FakeFaceAnalyzer()
    init_db(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def companion_enabled_client(tmp_path: Path):
    db_path = tmp_path / "companion.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path}",
        auto_create_tables=True,
        rate_limit_enabled=False,
        environment="test",
        debug=False,
        secret_key="test-secret",
        feature_companion_enabled=True,
    )
    app = create_app(settings)
    init_db(app.state.engine)
    with TestClient(app) as test_client:
        yield test_client
