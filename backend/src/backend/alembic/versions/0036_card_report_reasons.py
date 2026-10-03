"""Let a card report hold several quick reasons next to the free comment.

Revision ID: 0036
Revises: 0035

Before this a report had one comment: either a quick reason or the user's
own words. Old reports whose comment is a quick reason move it into reasons.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

# The quick reasons offered when this revision was written.
QUICK_REASONS = (
    "Phrase too long",
    "Wrong phrase boundary",
    "More than one unknown word",
    "I know this word",
    "Not a real word",
    "Wrong word form",
)
REASON_SEPARATOR = "; "


def upgrade() -> None:
    op.add_column(
        "card_reports",
        sa.Column("reasons", sa.Text, nullable=False, server_default="[]"),
    )
    conn = op.get_bind()
    for reason in QUICK_REASONS:
        conn.execute(
            sa.text(
                "UPDATE card_reports SET reasons = :reasons, comment = ''"
                " WHERE comment = :reason"
            ),
            {"reasons": json.dumps([reason]), "reason": reason},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, reasons, comment FROM card_reports")).all()
    for report_id, reasons, comment in rows:
        parts = [*json.loads(reasons), comment] if comment else json.loads(reasons)
        conn.execute(
            sa.text("UPDATE card_reports SET comment = :comment WHERE id = :id"),
            {"comment": REASON_SEPARATOR.join(parts), "id": report_id},
        )
    with op.batch_alter_table("card_reports") as batch:
        batch.drop_column("reasons")
