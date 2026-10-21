"""Only the screens read the stored projection, through CardStateQuery; the rules never read
it (spec §2, §3 principle 2)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend"
QUERY_REFERENCE = re.compile(
    r"\b(card_state_query|sqla_card_state_query|CardStateQuery|SqlaCardStateQuery)\b",
)
READERS = {
    "domain/ports/card_state_query.py",
    "infrastructure/persistence/sqla_card_state_query.py",
    "infrastructure/container.py",
    "application/utils/review_header.py",
    "application/utils/review_progress.py",
    "application/use_cases/get_review_documents.py",
    "application/use_cases/get_generation_status.py",
}
# The rules and the projection's own computation: what the projection is derived from must
# not read it.
RULES = (
    "domain/services/",
    "application/utils/decision_effects.py",
    "application/utils/user_vocabulary.py",
    "application/utils/card_state_projector.py",
    "application/utils/live_card_states.py",
)


def _referring() -> set[str]:
    return {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*.py")
        if "alembic" not in path.parts
        and QUERY_REFERENCE.search(path.read_text(encoding="utf-8"))
    }


@pytest.mark.unit
def test_only_the_screens_read_the_projection() -> None:
    assert sorted(_referring() - READERS) == []


@pytest.mark.unit
def test_no_rule_reads_the_projection() -> None:
    offenders = sorted(
        relative for relative in _referring() if relative.startswith(RULES)
    )
    assert offenders == []
