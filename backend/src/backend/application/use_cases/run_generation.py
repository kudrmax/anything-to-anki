from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import CardJobs, ReadyCards, target_for
from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import GenerationBlockedError, SourceNotFoundError
from backend.domain.services.generation_scope import in_scope
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.review_card import ReviewCard

if TYPE_CHECKING:
    from collections.abc import Sequence

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

        of_source = self._cards.of_source(source_id)
        ready = ReadyCards.of(of_source, self._candidate_sorter)
        cards = target.cards(of_source)
        jobs = CardJobs.of(self._job_repo, cards)
        chosen = [
            c for c in cards
            if in_scope(scope, target.state(c, target.job_of(jobs, c)), target.is_ready(ready, c))
        ]

        if scope == GenerationScope.ALL:
            for card in chosen:
                target.discard(card)
            chosen = self._as_now(source_id, chosen)

        ordered = self._in_order(chosen, sort_order, [source_id])
        queued = len(self._job_repo.enqueue([target.job(c) for c in ordered]))
        logger.info(
            "run_generation: queued (source_id=%d, kind=%s, scope=%s, total=%d, sort_order=%s)",
            source_id, kind.value, scope.value, queued, sort_order.value,
        )
        return queued

    def _as_now(self, source_id: int, cards: list[GenerationCard]) -> list[GenerationCard]:
        """The cards as their discards left them: a job carries the revision of the text it
        is queued for."""
        ids = {card.phrase_id for card in cards}
        return [card for card in self._cards.of_source(source_id) if card.phrase_id in ids]

    def _in_order(
        self,
        cards: list[GenerationCard],
        sort_order: CandidateSortOrder,
        source_order: Sequence[int],
    ) -> list[GenerationCard]:
        """Cards in the order the user picked, as the review list shows them: the cards of
        a word together."""
        by_phrase = {card.phrase_id: card for card in cards}
        arranged = self._candidate_sorter.arrange(
            [ReviewCard(word=card.word, occurrence=card.phrase) for card in cards],
            sort_order,
            source_order=source_order,
        )
        return [by_phrase[card.phrase_id] for card in arranged.cards]
