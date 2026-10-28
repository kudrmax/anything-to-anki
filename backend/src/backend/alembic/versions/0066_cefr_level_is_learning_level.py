"""The CEFR level setting is now the level the user is learning, not the last one they know:
"B1" used to mean "show B2 and above", now it means "show B1 and above". Every saved level
moves one up, so the same words stay suggested and nothing has to be analysed again. C2
has nothing above it and stays C2.

Revision ID: 0066
Revises: 0065
"""
from __future__ import annotations

from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def _shift(pairs: list[tuple[str, str]]) -> None:
    cases = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in pairs)
    op.execute(
        f"UPDATE settings SET value = CASE upper(trim(value)) {cases} ELSE value END "
        "WHERE key = 'cefr_level'",
    )


def upgrade() -> None:
    _shift(list(zip(_LEVELS, _LEVELS[1:], strict=False)))


def downgrade() -> None:
    _shift(list(zip(_LEVELS[1:], _LEVELS, strict=False)))
