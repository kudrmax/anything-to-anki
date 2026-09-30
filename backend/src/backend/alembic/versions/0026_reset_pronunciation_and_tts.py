"""Drop pronunciation and TTS audio that may belong to another word.

Revision ID: 0026
Revises: 0025

Before 0025, a candidate could inherit pronunciation and TTS rows through a
reused id. Unlike meanings (checked against their words) and media (rewritten
on processing), an audio file cannot be verified against the word it is
attached to, so every such row is suspect. Both are regenerated without AI
calls — from the dictionary and the local TTS model — so they are all dropped.

Audio already exported to Anki is not affected: Anki keeps its own copies.

Downgrade is a no-op: the dropped rows cannot be restored.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM candidate_pronunciations")
    op.execute("DELETE FROM candidate_tts")


def downgrade() -> None:
    pass
