"""Runtime settings, read from environment variables prefixed with GARLEAK_.

No credential has a real default. ORCID client credentials and the session secret
come from the environment (or a local .env that is never committed).
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GARLEAK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://garleak:garleak@localhost:5432/garleak"
    redis_url: str = "redis://localhost:6379/0"

    # Where the browser lands after login or logout.
    web_base_url: str = "http://localhost:3000"

    # Signed session cookie. Required in production. In development and test an
    # ephemeral random secret is generated, so sessions do not survive a restart.
    session_secret: SecretStr | None = None
    session_cookie_name: str = "garleak_session"
    session_cookie_secure: bool = False
    session_max_age_seconds: int = 14 * 24 * 3600

    # ORCID OAuth (authorization-code flow). Sandbox by default.
    orcid_base_url: str = "https://sandbox.orcid.org"
    orcid_client_id: str | None = None
    orcid_client_secret: SecretStr | None = None
    orcid_redirect_uri: str = "http://localhost:8000/auth/orcid/callback"
    orcid_scope: str = "/authenticate"

    # Storage and search. Wired in Docker Compose now, used from M1 onward.
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    s3_bucket: str = "garleak"
    typesense_url: str | None = None
    typesense_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.env == "production":
            if self.session_secret is None:
                raise ValueError("GARLEAK_SESSION_SECRET must be set in production")
            if not self.session_cookie_secure:
                raise ValueError("GARLEAK_SESSION_COOKIE_SECURE must be true in production")
        return self

    @property
    def orcid_configured(self) -> bool:
        return bool(self.orcid_client_id and self.orcid_client_secret)

    @property
    def orcid_authorize_url(self) -> str:
        return f"{self.orcid_base_url.rstrip('/')}/oauth/authorize"

    @property
    def orcid_token_url(self) -> str:
        return f"{self.orcid_base_url.rstrip('/')}/oauth/token"

    def session_secret_value(self) -> str:
        if self.session_secret is not None:
            return self.session_secret.get_secret_value()
        return _ephemeral_secret()


@lru_cache(maxsize=1)
def _ephemeral_secret() -> str:
    return secrets.token_urlsafe(48)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
