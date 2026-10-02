"""Backfill word_decisions from reviewed candidates.

Revision ID: 0032
Revises: 0031

Candidates marked known or to learn already carry the user's verdicts.
Phrasal verbs are left out: their frequency is not comparable with single
words. When a word was reviewed in several sources, the latest verdict wins.
"""
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT OR REPLACE INTO word_decisions (lemma, zipf_frequency, is_known, decided_at)
        SELECT lemma, zipf_frequency, status = 'known', CURRENT_TIMESTAMP
        FROM candidates
        WHERE status IN ('known', 'learn')
          AND is_phrasal_verb = 0
          AND instr(lemma, ' ') = 0
        ORDER BY id
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM word_decisions")
