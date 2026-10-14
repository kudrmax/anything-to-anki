"""What a source in the list lets the user do, and how far its review has got."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import REVIEWABLE_STATUSES
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.source_operation_kind import SourceOperationKind

EXPORTABLE_STATUSES = frozenset({SourceStatus.PARTIALLY_REVIEWED, SourceStatus.REVIEWED})
COMPLETE = 1.0
NOTHING_DONE = 0.0


def can_review(status: SourceStatus) -> bool:
    return status in REVIEWABLE_STATUSES


def can_export(status: SourceStatus) -> bool:
    """Something was decided there."""
    return status in EXPORTABLE_STATUSES


def can_delete(source: Source, busy_with: SourceOperationKind | None) -> bool:
    """A built-in source stays; no source goes while an operation holds it."""
    return not source.is_permanent and busy_with is None


def review_fraction(status: SourceStatus, progress: DecisionProgress) -> float:
    """The share of decided cards; a reviewed source is complete whatever its cards say."""
    if status is SourceStatus.REVIEWED:
        return COMPLETE
    return progress.decided / progress.total if progress.total else NOTHING_DONE
