from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import REVIEWABLE_STATUSES
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.entities.source import Source

_REBUILDABLE_STATUSES = REVIEWABLE_STATUSES | {SourceStatus.ERROR}


def available_operation(source: Source) -> SourceOperationKind | None:
    """What a processed source can be brought up to date with.

    A source with its own text is rebuilt; a topic is refreshed from the other sources,
    adding phrases only; the saved phrases have nothing to update.
    """
    if source.role is SourceRole.CONTENT and source.status in _REBUILDABLE_STATUSES:
        return SourceOperationKind.REBUILD
    if source.role is SourceRole.TOPIC and source.status in REVIEWABLE_STATUSES:
        return SourceOperationKind.REFRESH
    return None
