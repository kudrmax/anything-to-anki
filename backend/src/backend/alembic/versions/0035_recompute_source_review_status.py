"""Recompute source review statuses from candidate decisions.

Revision ID: 0035
Revises: 0034

Decisions made before the backend derived the review status left some
sources in a status that disagrees with their candidates. Same rule as
derive_review_status: a reviewable source with any decision becomes
partially_reviewed while something is pending, otherwise reviewed.

Downgrade is a no-op: the previous statuses were wrong and are not kept.
"""
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE sources
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM candidates c
                WHERE c.source_id = sources.id AND c.status = 'pending'
            ) THEN 'partially_reviewed'
            ELSE 'reviewed'
        END
        WHERE status IN ('done', 'partially_reviewed', 'reviewed')
          AND EXISTS (
            SELECT 1 FROM candidates c
            WHERE c.source_id = sources.id AND c.status != 'pending'
          )
        """
    )


def downgrade() -> None:
    pass
