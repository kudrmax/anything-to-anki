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
    """Статус ревью источника по оценкам его кандидатов; источники вне ревью не меняются.

    Не начатый источник остаётся не начатым, пока по нему нет ни одного решения.
    """
    if current not in REVIEWABLE_STATUSES:
        return current
    statuses = list(candidate_statuses)
    has_pending = any(status == CandidateStatus.PENDING for status in statuses)
    if not has_pending:
        return SourceStatus.REVIEWED
    has_decided = any(status != CandidateStatus.PENDING for status in statuses)
    if current == SourceStatus.DONE and not has_decided:
        return SourceStatus.DONE
    return SourceStatus.PARTIALLY_REVIEWED
