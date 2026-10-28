"""Settings nothing reads any more are dropped: ai_provider and enable_definitions.

Revision ID: 0069
Revises: 0068

Downgrade adds nothing back: the app never read these values.
"""
from __future__ import annotations

from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM settings WHERE key IN ('ai_provider', 'enable_definitions')")


def downgrade() -> None:
    pass
