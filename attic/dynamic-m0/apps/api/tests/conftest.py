from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from garleak_api.db import Base
from garleak_api.main import create_app
from garleak_api.settings import Settings

# Placeholder values only. Nothing here is a real credential.
TEST_CLIENT_ID = "APP-TESTCLIENT0000"
TEST_CLIENT_SECRET = "not-a-real-secret"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        session_secret="test-session-secret",
        orcid_client_id=TEST_CLIENT_ID,
        orcid_client_secret=TEST_CLIENT_SECRET,
        orcid_redirect_uri="http://testserver/auth/orcid/callback",
        web_base_url="http://localhost:3000",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://testserver") as c:
        yield c
