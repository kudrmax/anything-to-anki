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


def _column_exists(conn: sa.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table_name})"))  # noqa: S608
    return any(row[1] == column_name for row in rows)


def _table_exists(conn: sa.Connection, table_name: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"
    ), {"name": table_name})
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create jobs table (idempotent — skip if already exists)
    if not _table_exists(conn, "jobs"):
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
    # (only if status column still exists — idempotent)
    for table, job_type in [
        ("candidate_meanings", "meaning"),
        ("candidate_media", "media"),
        ("candidate_pronunciations", "pronunciation"),
    ]:
        if _column_exists(conn, table, "status"):
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
        if _column_exists(conn, table, "status"):
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
