"""Alembic migrations apply cleanly and match the ORM models (no drift)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import garleak_api.models  # noqa: F401
from garleak_api.db import Base

API_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_head_matches_models(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'm.db'}"
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []

    command.downgrade(cfg, "base")
