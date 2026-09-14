"""ORM models.

M0 defines only the account stub that ORCID login needs. The core objects (Paper,
Scratch, Version, Verification, Fix) arrive in M1 and follow SPEC.md and
packages/schema. Do not add them here ad hoc.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from garleak_api.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Account(Base):
    """An accountable human, keyed by ORCID iD.

    Institutional-email accounts and agent accounts (with a registered human
    operator) are M2 work. When they land, orcid_id becomes nullable and a
    separate identity table is the likely shape.
    """

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    orcid_id: Mapped[str] = mapped_column(String(19), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
