"""Only CardStateProjector receives the card state store: the projection has one writer, and
the rules never read it (spec §3, principle 2)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend"
STORE_REFERENCE = re.compile(
    r"\b(card_state_store|sqla_card_state_store|CardStateStore|SqlaCardStateStore)\b",
)
ALLOWED = {
    "application/utils/card_state_projector.py",
    "domain/ports/card_state_store.py",
    "infrastructure/container.py",
    "infrastructure/persistence/sqla_card_state_store.py",
}


@pytest.mark.unit
def test_only_the_projector_receives_the_card_state_store() -> None:
    offenders = sorted(
        relative
        for path in SOURCE_ROOT.rglob("*.py")
        if "alembic" not in path.parts
        and (relative := path.relative_to(SOURCE_ROOT).as_posix()) not in ALLOWED
        and STORE_REFERENCE.search(path.read_text(encoding="utf-8"))
    )
    assert offenders == []


@pytest.mark.unit
def test_the_container_hands_the_store_only_to_the_projector() -> None:
    container = (SOURCE_ROOT / "infrastructure" / "container.py").read_text(encoding="utf-8")
    built = [line.strip() for line in container.splitlines() if "SqlaCardStateStore(" in line]
    assert built == ["store=SqlaCardStateStore(session),"]
    method = container[container.index("def card_state_projector("):]
    assert "SqlaCardStateStore(session)" in method[: method.index("\n    def ")]
