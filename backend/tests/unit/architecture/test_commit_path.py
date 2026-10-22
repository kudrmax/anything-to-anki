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
# Writes a database of its own (the dictionary cache, rebuilt whole from the dictionary
# files), never the app's: no card state lives there for a write to keep fresh.
OTHER_DATABASE_WRITERS = ("backend/src/backend/cli/build_dict_cache.py",)

ORM_MODULE = "sqlalchemy.orm"
SQLALCHEMY_PREFIX = "sqlalchemy"
SESSION_NAMES = frozenset(
    {"Session", "sessionmaker", "scoped_session", "AsyncSession", "async_sessionmaker"}
)
TRANSACTION_METHODS = frozenset({"commit", "begin", "begin_nested"})
TRANSACTION_CALLABLES = TRANSACTION_METHODS | SESSION_NAMES

TRANSACTION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES, *OTHER_DATABASE_WRITERS)
SESSION_ALLOWED = (PERSISTENCE_DIR, API_DEPENDENCIES, CONTAINER)


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


def _offenders(kind: str, allowed: tuple[str, ...]) -> list[str]:
    find_lines = _transaction_lines if kind == "transaction" else _session_import_lines
    offenders: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith(ALEMBIC_DIR) or _is_allowed(relative, allowed):
            continue
        text = path.read_text(encoding="utf-8")
        source_lines = text.splitlines()
        offenders.extend(
            f"{relative}:{number}: {source_lines[number - 1].strip()}"
            for number in find_lines(ast.parse(text, filename=relative))
        )
    return offenders


@pytest.mark.unit
def test_no_transaction_outside_persistence() -> None:
    assert _offenders("transaction", TRANSACTION_ALLOWED) == []


@pytest.mark.unit
def test_no_session_outside_persistence_and_di() -> None:
    assert _offenders("session", SESSION_ALLOWED) == []


UNIT_OF_WORK = "backend/src/backend/infrastructure/persistence/sqla_unit_of_work.py"
# Transactions inside persistence that bypass the unit of work and its level change gate,
# each safe while the level is being changed for the reason given.
GATE_BYPASS_ALLOWED = (
    # Startup only, before any request or level change: frees what a restart interrupted.
    "backend/src/backend/infrastructure/persistence/database.py",
    # A cache the level change's own analysis fills; no other analysis runs meanwhile, as
    # every source operation's start is a gated write.
    "backend/src/backend/infrastructure/persistence/sqla_parse_cache.py",
    # Waits out the level change's lock before writing.
    "backend/src/backend/infrastructure/persistence/session_ai_usage_recorder.py",
)


@pytest.mark.unit
def test_every_transaction_inside_persistence_passes_the_gate_or_is_known() -> None:
    """A transaction of its own would write past a level change; a new one is either moved
    into the unit of work or listed here with why it is safe."""
    allowed = (
        *(prefix for prefix in TRANSACTION_ALLOWED if prefix != PERSISTENCE_DIR),
        UNIT_OF_WORK,
        *GATE_BYPASS_ALLOWED,
    )
    assert _offenders("transaction", allowed) == []
