"""Known and unknown words are asked about and marked only through UserVocabulary, whose
reads go through the request's knowledge scope."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend"
WORD_LIST_IMPORT = re.compile(
    r"\b(word_mark_repository|sqla_word_mark_repository)\b",
)
ALLOWED = {
    "application/utils/knowledge_scope.py",
    "application/utils/user_vocabulary.py",
    "domain/ports/__init__.py",
    "domain/ports/word_mark_repository.py",
    "infrastructure/container.py",
    "infrastructure/persistence/sqla_word_mark_repository.py",
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
