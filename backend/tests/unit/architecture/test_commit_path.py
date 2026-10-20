"""SqlaUnitOfWork.write() is the only way to open and commit a transaction: a commit that
bypasses it would leave stored card state stale. Session stays inside persistence and DI."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPO_ROOT / "backend" / "src" / "backend"
PERSISTENCE_DIR = "backend/src/backend/infrastructure/persistence/"
API_DEPENDENCIES = "backend/src/backend/infrastructure/api/dependencies.py"
CONTAINER = "backend/src/backend/infrastructure/container.py"
ALEMBIC_DIR = "backend/src/backend/alembic/"

ORM_MODULE = "sqlalchemy.orm"
SQLALCHEMY_PREFIX = "sqlalchemy"
SESSION_NAMES = frozenset(
    {"Session", "sessionmaker", "scoped_session", "AsyncSession", "async_sessionmaker"}
)
TRANSACTION_METHODS = frozenset({"commit", "begin", "begin_nested"})
TRANSACTION_CALLABLES = TRANSACTION_METHODS | SESSION_NAMES

TRANSACTION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES)
SESSION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES, CONTAINER)

# Files that offend today. Tasks 1.3-1.5 remove entries as they migrate; Task 1.6 empties both.
PENDING_TRANSACTIONS: frozenset[str] = frozenset({
    "backend/src/backend/cli/build_dict_cache.py",
    "backend/src/backend/infrastructure/container.py",
    "backend/src/backend/infrastructure/services/lazy_media_reconciler.py",
})
PENDING_SESSION_IMPORTS: frozenset[str] = frozenset({
    "backend/src/backend/infrastructure/api/background_rebuild_launcher.py",
    "backend/src/backend/infrastructure/api/routes/anki.py",
    "backend/src/backend/infrastructure/api/routes/card_reports.py",
    "backend/src/backend/infrastructure/api/routes/stats.py",
    "backend/src/backend/infrastructure/api/routes/usage.py",
    "backend/src/backend/infrastructure/api/routes/vocabulary.py",
    "backend/src/backend/infrastructure/queue/claimed_run.py",
    "backend/src/backend/infrastructure/services/lazy_media_reconciler.py",
})


def _is_allowed(relative: str, allowed: tuple[str, ...]) -> bool:
    return any(relative.startswith(prefix) for prefix in allowed)


def _is_sqlalchemy(module: str | None) -> bool:
    return module is not None and (
        module == SQLALCHEMY_PREFIX or module.startswith(SQLALCHEMY_PREFIX + ".")
    )


def _is_orm(module: str | None) -> bool:
    return module is not None and (module == ORM_MODULE or module.startswith(ORM_MODULE + "."))


def _session_import_lines(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            binds_session = _is_sqlalchemy(node.module) and any(
                alias.name in SESSION_NAMES for alias in node.names
            )
            binds_orm = node.module == SQLALCHEMY_PREFIX and any(
                alias.name == "orm" for alias in node.names
            )
            if binds_session or binds_orm:
                lines.append(node.lineno)
        elif isinstance(node, ast.Import) and any(_is_orm(alias.name) for alias in node.names):
            lines.append(node.lineno)
    return lines


def _sqlalchemy_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and _is_sqlalchemy(node.module):
            for alias in node.names:
                if alias.asname is not None:
                    aliases[alias.asname] = alias.name
    return aliases


def _called_name(call: ast.Call, aliases: dict[str, str]) -> str | None:
    function = call.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return aliases.get(function.id, function.id)
    return None


def _transaction_lines(tree: ast.AST) -> list[int]:
    aliases = _sqlalchemy_aliases(tree)
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _called_name(node, aliases) in TRANSACTION_CALLABLES
    )


def _scan(kind: str, allowed: tuple[str, ...]) -> dict[str, list[str]]:
    find_lines = _transaction_lines if kind == "transaction" else _session_import_lines
    offenders: dict[str, list[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(ALEMBIC_DIR) or _is_allowed(relative, allowed):
            continue
        text = path.read_text(encoding="utf-8")
        source_lines = text.splitlines()
        for number in find_lines(ast.parse(text, filename=relative)):
            offenders.setdefault(relative, []).append(
                f"{relative}:{number}: {source_lines[number - 1].strip()}"
            )
    return offenders


def _transaction_offenders() -> dict[str, list[str]]:
    return _scan("transaction", TRANSACTION_ALLOWED)


def _session_offenders() -> dict[str, list[str]]:
    return _scan("session", SESSION_ALLOWED)


def _new_offenders(found: dict[str, list[str]], pending: frozenset[str]) -> list[str]:
    return [
        entry
        for file, entries in sorted(found.items())
        if file not in pending
        for entry in entries
    ]


@pytest.mark.unit
def test_no_transaction_outside_persistence() -> None:
    assert _new_offenders(_transaction_offenders(), PENDING_TRANSACTIONS) == []


@pytest.mark.unit
def test_no_session_outside_persistence_and_di() -> None:
    assert _new_offenders(_session_offenders(), PENDING_SESSION_IMPORTS) == []


@pytest.mark.unit
def test_pending_lists_hold_only_offenders() -> None:
    clean_transactions = PENDING_TRANSACTIONS - _transaction_offenders().keys()
    clean_sessions = PENDING_SESSION_IMPORTS - _session_offenders().keys()
    assert sorted(clean_transactions) == []
    assert sorted(clean_sessions) == []
