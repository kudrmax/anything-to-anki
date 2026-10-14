from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import CardJobs, target_for
from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import GenerationBlockedError, SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.review_card import ReviewCard

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.generation_targets import (
        GenerationCard,
        GenerationCards,
        GenerationTarget,
    )
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.generation_kind import GenerationKind

logger = logging.getLogger(__name__)

# Cards already being generated are left alone in every scope: their job is about to
# deliver a fresh result anyway, and a second job would only duplicate the work.
_STATES_IN_SCOPE: dict[GenerationScope, frozenset[CardGenerationState]] = {
    GenerationScope.MISSING: frozenset({CardGenerationState.MISSING}),
    GenerationScope.FAILED: frozenset({CardGenerationState.FAILED}),
    GenerationScope.ALL: frozenset({
        CardGenerationState.DONE, CardGenerationState.FAILED, CardGenerationState.MISSING,
    }),
}


class RunGenerationUseCase:
    """Queues one kind of generation for the source's cards that fall into the scope."""

    def __init__(
        self,
        source_repo: SourceRepository,
        cards: GenerationCards,
        job_repo: JobRepository,
        candidate_sorter: CandidateSorter,
        targets: list[GenerationTarget],
        lock: SourceOperationLock,
    ) -> None:
        self._source_repo = source_repo
        self._cards = cards
        self._job_repo = job_repo
        self._candidate_sorter = candidate_sorter
        self._targets = targets
        self._lock = lock

    def execute(
        self,
        source_id: int,
        kind: GenerationKind,
        scope: GenerationScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> int:
        """Returns how many cards were queued."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        ensure_source_free(self._lock, source_id)
        target = target_for(self._targets, kind, source)
        video_downloading = self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.VIDEO_DOWNLOAD}),
        )
        blocker = target.blocker(source, video_downloading)
        if blocker is not None:
            raise GenerationBlockedError(source_id, blocker.value)

        cards = target.cards(self._cards.of_source(source_id))
        jobs = CardJobs.of(self._job_repo, cards)
        in_scope = _STATES_IN_SCOPE[scope]
        chosen = [c for c in cards if target.state(c, target.job_of(jobs, c)) in in_scope]

        if scope == GenerationScope.ALL:
            for card in chosen:
                target.discard(card)

        ordered = self._in_order(chosen, sort_order)
        queued = len(self._job_repo.enqueue([target.job(c) for c in ordered]))
        logger.info(
            "run_generation: queued (source_id=%d, kind=%s, scope=%s, total=%d, sort_order=%s)",
            source_id, kind.value, scope.value, queued, sort_order.value,
        )
        return queued

    def _in_order(
        self, cards: list[GenerationCard], sort_order: CandidateSortOrder,
    ) -> list[GenerationCard]:
        """Cards in the order the user picked, as the review list shows them: the cards of
        a word together."""
        by_phrase = {card.phrase_id: card for card in cards}
        arranged = self._candidate_sorter.arrange(
            [ReviewCard(word=card.word, occurrence=card.phrase) for card in cards],
            sort_order,
        )
        return [by_phrase[card.phrase_id] for card in arranged.cards]
