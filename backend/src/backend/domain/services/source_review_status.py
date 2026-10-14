from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.value_objects.decision_progress import DecisionProgress

REVIEWABLE_STATUSES = frozenset({
    SourceStatus.DONE,
    SourceStatus.PARTIALLY_REVIEWED,
    SourceStatus.REVIEWED,
})


def derive_review_status(current: SourceStatus, progress: DecisionProgress) -> SourceStatus:
    """Статус ревью источника по его прогрессу; источники вне ревью не меняются.

    Не начатый источник остаётся не начатым, пока по нему нет ни одного решения.
    """
    if current not in REVIEWABLE_STATUSES:
        return current
    if progress.decided == progress.total:
        return SourceStatus.REVIEWED
    if current == SourceStatus.DONE and progress.decided == 0:
        return SourceStatus.DONE
    return SourceStatus.PARTIALLY_REVIEWED
