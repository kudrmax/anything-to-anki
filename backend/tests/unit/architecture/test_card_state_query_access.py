"""Only the screens read the stored projection, through CardStateQuery. The rules never read
it, nor do the live references it is checked against, not even through another module
(spec §2, §3 principle 2)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src" / "backend"
PACKAGE = "backend"
QUERY_REFERENCE = re.compile(
    r"\b(card_state_query|sqla_card_state_query|CardStateQuery|SqlaCardStateQuery)\b",
)
READERS = {
    "domain/ports/card_state_query.py",
    "infrastructure/persistence/sqla_card_state_query.py",
    "infrastructure/container.py",
    "application/utils/review_progress.py",
    "application/use_cases/get_review_documents.py",
    "application/use_cases/get_generation_status.py",
    "application/utils/review_answer.py",
    "application/utils/review_ordering.py",
    "application/utils/review_updates.py",
    "application/use_cases/review_mutation.py",
    "application/utils/review_text.py",
}
# What reads the projection, directly or as a screen built on it.
PROJECTION_READERS = {
    "backend.domain.ports.card_state_query",
    "backend.infrastructure.persistence.sqla_card_state_query",
    "backend.application.utils.review_progress",
    "backend.application.utils.review_header",
    "backend.application.utils.review_answer",
    "backend.application.use_cases.open_review",
    "backend.application.use_cases.review_window",
    "backend.application.utils.review_ordering",
    "backend.application.utils.review_updates",
    "backend.application.use_cases.review_mutation",
    "backend.application.utils.review_text",
}
# The rules, the projection's own computation, and the live references it is checked
# against: none may reach a reader of the projection through any chain of imports.
NEVER_READING = (
    "backend.domain.services",
    "backend.application.utils.decision_effects",
    "backend.application.utils.user_vocabulary",
    "backend.application.utils.card_state_projector",
    "backend.application.utils.export_queue",
    "backend.application.utils.live_card_states",
    "backend.application.utils.live_generation_status",
    "backend.application.utils.live_source_progress",
    "backend.application.utils.card_views",
)


def _module_of(path: Path) -> str:
    parts = path.relative_to(SOURCE_ROOT.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _modules() -> dict[str, Path]:
    return {
        _module_of(path): path
        for path in SOURCE_ROOT.rglob("*.py") if "alembic" not in path.parts
    }


def imported(source: str, modules: set[str]) -> set[str]:
    """The package's modules `source` imports, inside TYPE_CHECKING too: `import a.b`,
    `import a.b as c`, `from a import b` (module b or a name of a), `from a.b import c`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found |= {f"{node.module}.{alias.name}" for alias in node.names}
    return {name for name in found if name in modules}


def reached_readers(start: str, graph: dict[str, set[str]]) -> list[list[str]]:
    """Every chain of imports from `start` to a reader of the projection, one per reader."""
    chains: dict[str, list[str]] = {}
    queue = [[start]]
    seen = {start}
    while queue:
        chain = queue.pop(0)
        for target in sorted(graph.get(chain[-1], set())):
            if target in seen:
                continue
            seen.add(target)
            if target in PROJECTION_READERS:
                chains.setdefault(target, [*chain, target])
            else:
                queue.append([*chain, target])
    return list(chains.values())


def _graph() -> dict[str, set[str]]:
    modules = _modules()
    names = set(modules)
    return {
        module: imported(path.read_text(encoding="utf-8"), names)
        for module, path in modules.items()
    }


def _offending_chains(graph: dict[str, set[str]]) -> list[str]:
    starts = [
        module for module in graph
        if module.startswith(NEVER_READING)
        and (module in NEVER_READING or module.split(".")[-2] == "services")
    ]
    assert len(starts) >= len(NEVER_READING), "a module of NEVER_READING is gone"
    return sorted(
        " -> ".join(chain) for start in starts for chain in reached_readers(start, graph)
    )


@pytest.mark.unit
def test_only_the_screens_read_the_projection() -> None:
    referring = {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*.py")
        if "alembic" not in path.parts
        and QUERY_REFERENCE.search(path.read_text(encoding="utf-8"))
    }
    assert sorted(referring - READERS) == []
    assert sorted(READERS - referring) == []


@pytest.mark.unit
def test_no_rule_nor_live_reference_reaches_the_projection() -> None:
    assert _offending_chains(_graph()) == []


@pytest.mark.unit
def test_an_import_through_another_module_is_caught() -> None:
    """A rule importing a harmless module that imports the projection's reader."""
    graph = _graph()
    graph["backend.application.utils.user_vocabulary"] |= {"backend.planted.middle"}
    graph["backend.planted.middle"] = {"backend.application.utils.review_header"}
    assert (
        "backend.application.utils.user_vocabulary -> backend.planted.middle"
        " -> backend.application.utils.review_header"
    ) in _offending_chains(graph)


@pytest.mark.unit
def test_every_form_of_import_is_read() -> None:
    modules = {"backend.a", "backend.a.b", "backend.c"}
    source = (
        "import backend.a.b as alias\n"
        "from backend.a import b\n"
        "from backend import c\n"
        "if TYPE_CHECKING:\n    from backend.a.b import Thing\n"
    )
    assert imported(source, modules) == modules
