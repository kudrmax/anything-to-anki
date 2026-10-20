"""Jobs get params: what a job needs besides its target.

Revision ID: 0053
Revises: 0052

A meaning follow-up asked from Review goes through the queue like every AI call;
its job keeps the question as JSON in `params`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("params", sa.Text, nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE job_type = 'meaning_follow_up'")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("params")
