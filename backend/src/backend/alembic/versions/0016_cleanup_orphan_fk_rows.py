"""Clean up orphan rows in tables with FK to candidates.

SQLite had PRAGMA foreign_keys OFF (default), so ON DELETE CASCADE on
ForeignKey columns was silently ignored. Any previous candidate deletion
left orphan rows in cefr_breakdowns and anki_synced_cards.

Revision ID: 0016
Revises: 0015
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM cefr_breakdowns
        WHERE candidate_id NOT IN (SELECT id FROM candidates)
    """)
    op.execute("""
        DELETE FROM anki_synced_cards
        WHERE candidate_id NOT IN (SELECT id FROM candidates)
    """)


def downgrade() -> None:
    pass  # deleted orphans cannot be restored
