"""Add jobs table, migrate non-terminal enrichments, drop status/error columns.

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(30), nullable=False, index=True),
        sa.Column(
            "candidate_id",
            sa.Integer,
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, default="queued", index=True,
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
    )

    # 2. Migrate non-terminal enrichments to jobs table as FAILED
    conn = op.get_bind()
    for table, job_type in [
        ("candidate_meanings", "meaning"),
        ("candidate_media", "media"),
        ("candidate_pronunciations", "pronunciation"),
    ]:
        conn.execute(sa.text(f"""
            INSERT INTO jobs (job_type, candidate_id, source_id, status, error, created_at)
            SELECT '{job_type}', t.candidate_id, c.source_id, 'failed',
                   COALESCE(t.error, 'interrupted by queue migration'),
                   CURRENT_TIMESTAMP
            FROM {table} t
            JOIN candidates c ON c.id = t.candidate_id
            WHERE t.status IN ('failed', 'queued', 'running')
        """))

    # 3. Drop status/error columns from enrichment tables
    for table in [
        "candidate_meanings",
        "candidate_media",
        "candidate_pronunciations",
    ]:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("status")
            batch_op.drop_column("error")


def downgrade() -> None:
    for table in [
        "candidate_meanings",
        "candidate_media",
        "candidate_pronunciations",
    ]:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("status", sa.String(20), nullable=False, server_default="done"),
            )
            batch_op.add_column(sa.Column("error", sa.Text, nullable=True))

    op.drop_table("jobs")
