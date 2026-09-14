"""accounts stub for ORCID login

Revision ID: 0001
Revises:
Create Date: 2026-09-14

M0 only. The core objects (Paper, Scratch, Version, Verification, Fix) come in M1.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("orcid_id", sa.String(length=19), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(op.f("ix_accounts_orcid_id"), "accounts", ["orcid_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_orcid_id"), table_name="accounts")
    op.drop_table("accounts")
