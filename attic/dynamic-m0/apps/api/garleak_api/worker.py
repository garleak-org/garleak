"""Celery worker. Run with `celery -A garleak_api.worker worker --loglevel=info`.

M0 has one task, `garleak.ping`, which exists to prove the broker wiring. Real jobs
(automated pre-screen, citecheck runs, digests) arrive with their milestones.
"""

from __future__ import annotations

from celery import Celery

from garleak_api.settings import Settings, get_settings


def make_celery(settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    app = Celery("garleak", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = make_celery()


@celery_app.task(name="garleak.ping")
def ping() -> str:
    return "pong"
