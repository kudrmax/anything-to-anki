"""SqlaUnitOfWork.write() is the only way to open and commit a transaction: a commit that
bypasses it would leave stored card state stale. Session stays inside persistence and DI."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPO_ROOT / "backend" / "src" / "backend"
PERSISTENCE_DIR = "backend/src/backend/infrastructure/persistence/"
API_DEPENDENCIES = "backend/src/backend/infrastructure/api/dependencies.py"
CONTAINER = "backend/src/backend/infrastructure/container.py"
ALEMBIC_DIR = "backend/src/backend/alembic/"

TRANSACTION_CALL = re.compile(r"\.commit\(|\.begin\(|begin_nested\(|sessionmaker\(|\bSession\(")
SESSION_IMPORT = re.compile(r"^\s*from\s+sqlalchemy\.orm\s+import\s+.*\bSession\b")

TRANSACTION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES)
SESSION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES, CONTAINER)

# Files that offend today. Tasks 1.3-1.5 remove entries as they migrate; Task 1.6 empties both.
PENDING_TRANSACTIONS: frozenset[str] = frozenset({
    "backend/src/backend/application/use_cases/manage_settings.py",
    "backend/src/backend/application/use_cases/process_source.py",
    "backend/src/backend/application/use_cases/rebuild_source.py",
    "backend/src/backend/application/use_cases/refresh_topic.py",
    "backend/src/backend/application/use_cases/scope_operation.py",
    "backend/src/backend/application/utils/source_rebuilder.py",
    "backend/src/backend/cli/build_dict_cache.py",
    "backend/src/backend/infrastructure/api/background.py",
    "backend/src/backend/infrastructure/api/routes/bootstrap.py",
    "backend/src/backend/infrastructure/api/routes/collections.py",
    "backend/src/backend/infrastructure/api/routes/export.py",
    "backend/src/backend/infrastructure/api/routes/generation.py",
    "backend/src/backend/infrastructure/api/routes/known_words.py",
    "backend/src/backend/infrastructure/api/routes/phrases.py",
    "backend/src/backend/infrastructure/api/routes/queue.py",
    "backend/src/backend/infrastructure/api/routes/review.py",
    "backend/src/backend/infrastructure/api/routes/settings.py",
    "backend/src/backend/infrastructure/api/routes/sources.py",
    "backend/src/backend/infrastructure/api/routes/unknown_words.py",
    "backend/src/backend/infrastructure/api/routes/words.py",
    "backend/src/backend/infrastructure/container.py",
    "backend/src/backend/infrastructure/services/lazy_media_reconciler.py",
})
PENDING_SESSION_IMPORTS: frozenset[str] = frozenset({
    "backend/src/backend/infrastructure/api/background.py",
    "backend/src/backend/infrastructure/api/background_rebuild_launcher.py",
    "backend/src/backend/infrastructure/api/routes/anki.py",
    "backend/src/backend/infrastructure/api/routes/bootstrap.py",
    "backend/src/backend/infrastructure/api/routes/card_reports.py",
    "backend/src/backend/infrastructure/api/routes/collections.py",
    "backend/src/backend/infrastructure/api/routes/export.py",
    "backend/src/backend/infrastructure/api/routes/generation.py",
    "backend/src/backend/infrastructure/api/routes/known_words.py",
    "backend/src/backend/infrastructure/api/routes/operations.py",
    "backend/src/backend/infrastructure/api/routes/phrases.py",
    "backend/src/backend/infrastructure/api/routes/queue.py",
    "backend/src/backend/infrastructure/api/routes/review.py",
    "backend/src/backend/infrastructure/api/routes/settings.py",
    "backend/src/backend/infrastructure/api/routes/sources.py",
    "backend/src/backend/infrastructure/api/routes/stats.py",
    "backend/src/backend/infrastructure/api/routes/unknown_words.py",
    "backend/src/backend/infrastructure/api/routes/usage.py",
    "backend/src/backend/infrastructure/api/routes/vocabulary.py",
    "backend/src/backend/infrastructure/api/routes/words.py",
    "backend/src/backend/infrastructure/queue/claimed_run.py",
    "backend/src/backend/infrastructure/services/lazy_media_reconciler.py",
})


def _is_allowed(relative: str, allowed: tuple[str, ...]) -> bool:
    return any(relative == prefix or relative.startswith(prefix) for prefix in allowed)


def _scan(pattern: re.Pattern[str], allowed: tuple[str, ...]) -> dict[str, list[str]]:
    offenders: dict[str, list[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(ALEMBIC_DIR) or _is_allowed(relative, allowed):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.setdefault(relative, []).append(f"{relative}:{number}: {line.strip()}")
    return offenders


def _new_offenders(found: dict[str, list[str]], pending: frozenset[str]) -> list[str]:
    return [
        entry
        for file, entries in sorted(found.items())
        if file not in pending
        for entry in entries
    ]


@pytest.mark.unit
def test_no_transaction_outside_persistence() -> None:
    found = _scan(TRANSACTION_CALL, TRANSACTION_ALLOWED)
    assert _new_offenders(found, PENDING_TRANSACTIONS) == []


@pytest.mark.unit
def test_no_session_outside_persistence_and_di() -> None:
    found = _scan(SESSION_IMPORT, SESSION_ALLOWED)
    assert _new_offenders(found, PENDING_SESSION_IMPORTS) == []


@pytest.mark.unit
def test_pending_lists_hold_only_offenders() -> None:
    clean_transactions = PENDING_TRANSACTIONS - _scan(TRANSACTION_CALL, TRANSACTION_ALLOWED).keys()
    clean_sessions = PENDING_SESSION_IMPORTS - _scan(SESSION_IMPORT, SESSION_ALLOWED).keys()
    assert sorted(clean_transactions) == []
    assert sorted(clean_sessions) == []
