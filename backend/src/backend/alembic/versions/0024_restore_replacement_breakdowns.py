"""Restore CEFR breakdown and usage for candidates replaced with an example.

Revision ID: 0024
Revises: 0023

"Replace with example" used to create the new candidate without the CEFR
breakdown and usage distribution of the one it replaced. The CEFR level is
derived from the breakdown on load, so such candidates lost their level.

Each affected candidate gets a copy from the earliest candidate of the same
source, lemma and POS that has a breakdown — the one it was created from.

Idempotent: only touches candidates that still have no breakdown.

Downgrade is a no-op: the copied rows are valid on the previous schema and
cannot be told apart from breakdowns saved by the fixed use case.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORIGINAL_ID = """
    SELECT MIN(o.id)
    FROM candidates o
    JOIN cefr_breakdowns ob ON ob.candidate_id = o.id
    WHERE o.source_id = r.source_id AND o.lemma = r.lemma AND o.pos = r.pos
"""

_WITHOUT_BREAKDOWN = """
    r.has_custom_context_fragment = 1
    AND NOT EXISTS (SELECT 1 FROM cefr_breakdowns x WHERE x.candidate_id = r.id)
"""


def upgrade() -> None:
    conn = op.get_bind()

    # Usage first: once the breakdown is copied the candidate no longer matches.
    conn.execute(text(
        f"""
        UPDATE candidates AS r
        SET usage_distribution = (
            SELECT o.usage_distribution FROM candidates o WHERE o.id = ({_ORIGINAL_ID})
        )
        WHERE r.usage_distribution IS NULL AND {_WITHOUT_BREAKDOWN}
        """
    ))

    conn.execute(text(
        f"""
        INSERT INTO cefr_breakdowns
            (candidate_id, decision_method, cambridge, cefrpy,
             efllex_distribution, oxford, kelly)
        SELECT r.id, b.decision_method, b.cambridge, b.cefrpy,
               b.efllex_distribution, b.oxford, b.kelly
        FROM candidates r
        JOIN cefr_breakdowns b ON b.candidate_id = ({_ORIGINAL_ID})
        WHERE {_WITHOUT_BREAKDOWN}
        """
    ))


def downgrade() -> None:
    pass
