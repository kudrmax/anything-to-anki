"""Move sources made before documents onto documents.

Revision ID: 0045
Revises: 0044

Applied to both copies of the app (prod and dev) on 2026-10-13: every source made before
documents got one from its cleaned text, and its candidates the places of their phrase and
target. The code was written for the data of that day and is gone; the revision stays to
keep the chain. A new database has no sources to move.
"""

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
