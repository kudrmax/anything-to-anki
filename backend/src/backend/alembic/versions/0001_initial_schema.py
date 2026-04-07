"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-07

Brownfield baseline: creates all current tables only if they don't exist yet.
For existing production databases all tables are already present — checkfirst=True
makes every create_all a no-op, and Alembic simply stamps the revision.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Import here to avoid issues at Alembic import time
    from backend.infrastructure.persistence import models  # noqa: F401
    from backend.infrastructure.persistence.database import Base

    bind = op.get_bind()
    # Exclude tables introduced by later migrations so they don't conflict.
    # Tables added in 0002+: anki_synced_cards
    # Tables added in 0003+: candidate_meanings, candidate_media
    added_later = {"anki_synced_cards", "candidate_meanings", "candidate_media"}
    tables = [t for name, t in Base.metadata.tables.items() if name not in added_later]
    Base.metadata.create_all(bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    pass  # intentionally no-op: dropping all tables is too destructive
