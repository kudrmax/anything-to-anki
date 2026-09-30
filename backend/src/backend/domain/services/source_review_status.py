from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

REVIEWABLE_STATUSES = frozenset({
    SourceStatus.DONE,
    SourceStatus.PARTIALLY_REVIEWED,
    SourceStatus.REVIEWED,
})


def derive_review_status(
    current: SourceStatus, candidate_statuses: Iterable[CandidateStatus],
) -> SourceStatus:
    """Статус ревью источника по оценкам его кандидатов; источники вне ревью не меняются."""
    if current not in REVIEWABLE_STATUSES:
        return current
    has_pending = any(status == CandidateStatus.PENDING for status in candidate_statuses)
    return SourceStatus.PARTIALLY_REVIEWED if has_pending else SourceStatus.REVIEWED
