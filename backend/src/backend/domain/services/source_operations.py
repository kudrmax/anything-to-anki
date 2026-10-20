from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from backend.domain.entities.source import Source

_REBUILDABLE_STATUSES = frozenset({SourceStatus.DONE, SourceStatus.ERROR})


_BUSY_NAME: dict[SourceOperationKind, str] = {
    SourceOperationKind.PROCESS: "processing",
    SourceOperationKind.UPDATE: "word search",
    SourceOperationKind.RECUT: "reprocessing",
    SourceOperationKind.PREVIEW: "count of changes",
    SourceOperationKind.REFRESH: "refresh",
}


def available_operations(source: Source) -> tuple[SourceOperationKind, ...]:
    """What a processed source can be brought up to date with, in menu order. While another
    operation holds the source, they are still offered, but can't start (see `operation_hint`).

    A source with its own text is rebuilt, its phrases kept or cut anew; a topic is
    refreshed from the other sources, adding phrases only, and rebuilt, which moves the
    sections of its phrases; the saved phrases are only rebuilt that way.
    """
    if source.role is SourceRole.CONTENT and source.status in _REBUILDABLE_STATUSES:
        return (SourceOperationKind.UPDATE, SourceOperationKind.RECUT)
    if source.role is SourceRole.TOPIC and source.status is SourceStatus.DONE:
        return (SourceOperationKind.REFRESH, SourceOperationKind.UPDATE)
    if source.role is SourceRole.SAVED_PHRASES:
        return (SourceOperationKind.UPDATE,)
    return ()


REBUILD_OPERATION: Mapping[RebuildMode, SourceOperationKind] = MappingProxyType({
    RebuildMode.UPDATE: SourceOperationKind.UPDATE,
    RebuildMode.RECUT: SourceOperationKind.RECUT,
})


def operation_hint(busy_with: SourceOperationKind | None) -> str | None:
    """Why the operation can't start on a busy source."""
    if busy_with is None:
        return None
    return f"Wait until the {_BUSY_NAME[busy_with]} finishes"


_MENU_ORDER = (
    SourceOperationKind.REFRESH, SourceOperationKind.UPDATE, SourceOperationKind.RECUT,
)


@dataclass(frozen=True)
class OperationsOffer:
    """What a set of sources can be brought up to date with, in menu order, whether it can
    start now and, if not, why."""

    operations: tuple[SourceOperationKind, ...]
    can_start: bool
    hint: str | None


def operations_offer(
    sources: Iterable[Source], busy: Mapping[int, SourceOperationKind],
) -> OperationsOffer:
    """A source is a set of one. A set offers what any of its sources offers; it can start
    while one of the sources offering it is free, and a set offering nothing can start
    while one of its sources is free, as a single source does."""
    members = list(sources)
    offered = {op for source in members for op in available_operations(source)}
    offering = [source for source in members if available_operations(source)]
    pool = offering or members
    held = [busy[s.id] for s in pool if s.id is not None and s.id in busy]
    can_start = len(held) < len(pool)
    return OperationsOffer(
        operations=tuple(op for op in _MENU_ORDER if op in offered),
        can_start=can_start,
        hint=None if can_start or not held else operation_hint(held[0]),
    )


_BUSY_CAPTION: dict[SourceOperationKind, str] = {
    SourceOperationKind.PROCESS: "Processing…",
    SourceOperationKind.UPDATE: "Finding words again…",
    SourceOperationKind.RECUT: "Processing again…",
    SourceOperationKind.PREVIEW: "Counting what will change…",
    SourceOperationKind.REFRESH: "Refreshing…",
}


def busy_caption(kind: SourceOperationKind) -> str:
    """What the user is told while the operation runs."""
    return _BUSY_CAPTION[kind]
