"""What a source in the list lets the user do, and how far its review has got."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    DomainError,
    PermanentSourceError,
    SourceIsProcessingError,
)
from backend.domain.services.source_review_status import REVIEWABLE_STATUSES
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.value_objects.decision_progress import DecisionProgress

EXPORTABLE_STATUSES = frozenset({SourceStatus.PARTIALLY_REVIEWED, SourceStatus.REVIEWED})
COMPLETE = 1.0
NOTHING_DONE = 0.0


def can_review(status: SourceStatus) -> bool:
    return status in REVIEWABLE_STATUSES


def can_export(status: SourceStatus) -> bool:
    """Something was decided there."""
    return status in EXPORTABLE_STATUSES


def ensure_deletable(source: Source, busy_with: SourceOperationKind | None) -> None:
    """A built-in source stays; no source goes while an operation holds it."""
    assert source.id is not None
    if source.is_permanent:
        raise PermanentSourceError(source.id)
    if busy_with is not None:
        raise SourceIsProcessingError(source.id)


def can_delete(source: Source, busy_with: SourceOperationKind | None) -> bool:
    try:
        ensure_deletable(source, busy_with)
    except DomainError:
        return False
    return True


def review_fraction(status: SourceStatus, progress: DecisionProgress) -> float:
    """The share of decided cards; a reviewed source is complete whatever its cards say."""
    if status is SourceStatus.REVIEWED:
        return COMPLETE
    return progress.decided / progress.total if progress.total else NOTHING_DONE


_BUSY_CAPTION: dict[SourceOperationKind, str] = {
    SourceOperationKind.PROCESS: "Processing…",
    SourceOperationKind.REBUILD: "Rebuilding…",
    SourceOperationKind.PREVIEW: "Checking what a rebuild changes…",
    SourceOperationKind.REFRESH: "Refreshing…",
}


def progress_caption(
    status: SourceStatus,
    cards: int,
    progress: DecisionProgress,
    learn_count: int,
    busy_with: SourceOperationKind | None,
) -> str:
    """The line under a source's progress: what it is busy with, or where its review is."""
    if busy_with is not None:
        return _BUSY_CAPTION[busy_with]
    if cards == 0:
        return "Nothing to learn"
    if progress.total == 0:
        return "Nothing ready"
    if status is SourceStatus.REVIEWED:
        return f"{learn_count} to learn"
    if progress.decided > 0:
        return f"{progress.decided} of {progress.total} decided"
    return f"{progress.total} phrases"
