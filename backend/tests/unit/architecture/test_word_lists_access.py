"""Known and unknown words are asked about and marked only through UserVocabulary."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend"
WORD_LIST_IMPORT = re.compile(
    r"\b(known_word_repository|unknown_word_repository|"
    r"sqla_known_word_repository|sqla_unknown_word_repository)\b",
)
ALLOWED = {
    "application/utils/user_vocabulary.py",
    "domain/ports/__init__.py",
    "domain/ports/known_word_repository.py",
    "domain/ports/unknown_word_repository.py",
    "infrastructure/container.py",
    "infrastructure/persistence/sqla_known_word_repository.py",
    "infrastructure/persistence/sqla_unknown_word_repository.py",
}


@pytest.mark.unit
def test_only_user_vocabulary_reaches_the_word_lists() -> None:
    offenders = sorted(
        relative
        for path in SOURCE_ROOT.rglob("*.py")
        if "alembic" not in path.parts
        and (relative := path.relative_to(SOURCE_ROOT).as_posix()) not in ALLOWED
        and WORD_LIST_IMPORT.search(path.read_text(encoding="utf-8"))
    )
    assert offenders == []
