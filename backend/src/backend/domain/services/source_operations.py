from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import REVIEWABLE_STATUSES
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.entities.source import Source

_REBUILDABLE_STATUSES = REVIEWABLE_STATUSES | {SourceStatus.ERROR}


_BUSY_NAME: dict[SourceOperationKind, str] = {
    SourceOperationKind.PROCESS: "processing",
    SourceOperationKind.REBUILD: "rebuild",
    SourceOperationKind.PREVIEW: "rebuild preview",
    SourceOperationKind.REFRESH: "refresh",
}


def available_operation(source: Source) -> SourceOperationKind | None:
    """What a processed source can be brought up to date with. While another operation
    holds the source, it is still offered, but can't start (see `operation_hint`).

    A source with its own text is rebuilt; a topic is refreshed from the other sources,
    adding phrases only; the saved phrases have nothing to update.
    """
    if source.role is SourceRole.CONTENT and source.status in _REBUILDABLE_STATUSES:
        return SourceOperationKind.REBUILD
    if source.role is SourceRole.TOPIC and source.status in REVIEWABLE_STATUSES:
        return SourceOperationKind.REFRESH
    return None


def operation_hint(busy_with: SourceOperationKind | None) -> str | None:
    """Why the operation can't start on a busy source."""
    if busy_with is None:
        return None
    return f"Wait until the {_BUSY_NAME[busy_with]} finishes"


_BUSY_CAPTION: dict[SourceOperationKind, str] = {
    SourceOperationKind.PROCESS: "Processing…",
    SourceOperationKind.REBUILD: "Rebuilding…",
    SourceOperationKind.PREVIEW: "Checking what a rebuild changes…",
    SourceOperationKind.REFRESH: "Refreshing…",
}


def busy_caption(kind: SourceOperationKind) -> str:
    """What the user is told while the operation runs."""
    return _BUSY_CAPTION[kind]
