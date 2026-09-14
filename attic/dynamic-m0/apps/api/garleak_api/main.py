"""FastAPI application factory.

Run with `uvicorn --factory garleak_api.main:create_app`.
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from garleak_api import __version__
from garleak_api.db import make_engine, make_sessionmaker
from garleak_api.orcid import router as auth_router
from garleak_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(title="Garleak API", version=__version__)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    # SameSite=lax is required: the ORCID callback is a cross-site top-level GET that
    # must carry the cookie holding the OAuth state.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_value(),
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        """Liveness only. Does not touch the database or Redis."""
        return {"status": "ok", "service": "garleak-api", "version": __version__}

    app.include_router(auth_router)
    return app
