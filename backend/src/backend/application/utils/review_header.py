from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.review_dtos import ReviewHeaderDTO
from backend.application.dto.source_dtos import ProgressDTO
from backend.domain.services.source_review_status import (
    derive_review_status,
    stored_status_of_set,
)
from backend.domain.value_objects.decision_progress import DecisionProgress

if TYPE_CHECKING:
    from backend.application.utils.review_progress import ReviewProgress
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.value_objects.source_scope import SourceScope


class ReviewHeader:
    """What the review screen shows above the cards, for the whole set of sources: read
    from the stored projection, without the cards."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        review_progress: ReviewProgress,
        card_query: CardQuery,
        lock: SourceOperationLock,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._review_progress = review_progress
        self._card_query = card_query
        self._lock = lock

    def of(self, scope: SourceScope) -> ReviewHeaderDTO:
        sources = self._scope_resolver.reviewable_sources(scope)
        ids = [s.id for s in sources if s.id is not None]
        progress = sum(
            (found.progress for found in self._review_progress.of_sources(ids).values()),
            DecisionProgress(),
        )
        operations = self._lock.operations()
        return ReviewHeaderDTO(
            scope=scope.token,
            title=self._scope_resolver.title(scope),
            status=derive_review_status(
                stored_status_of_set(s.status for s in sources), progress,
            ).value,
            progress=ProgressDTO.of(progress),
            learn_count=sum(self._card_query.learn_counts(ids).values()),
            busy=any(source_id in operations for source_id in ids),
        )
