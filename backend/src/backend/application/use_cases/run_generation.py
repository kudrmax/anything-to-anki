from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.constants import GENERATION_RUN_CHUNK
from backend.application.utils.generation_targets import CardJobs, ReadyCards, target_for
from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import (
    GenerationBlockedError,
    GenerationNotSupportedError,
    SourceOperationBusyError,
)
from backend.domain.services.generation_scope import in_scope, replaces_results
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
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
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.job import Job
    from backend.domain.entities.source import Source
    from backend.domain.exceptions import DomainError
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.generation_kind import GenerationKind
    from backend.domain.value_objects.generation_scope import GenerationScope
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)

# Why a source of a set sits a run out: busy, no use for the kind, or held back.
_SKIPPED = (SourceOperationBusyError, GenerationNotSupportedError, GenerationBlockedError)


class RunGenerationUseCase:
    """Queues one kind of generation for the cards of a set of sources that fall into the
    chosen cards. A source that can't run it now is skipped; the set fails only when none
    of its sources could."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        cards: GenerationCards,
        job_repo: JobRepository,
        candidate_sorter: CandidateSorter,
        targets: list[GenerationTarget],
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._scope_resolver = scope_resolver
        self._cards = cards
        self._job_repo = job_repo
        self._candidate_sorter = candidate_sorter
        self._targets = targets
        self._lock = lock

    def execute(
        self,
        scope: SourceScope,
        kind: GenerationKind,
        cards: GenerationScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> int:
        """Returns how many cards were queued. The cards are chosen in a read, and queued in
        write transactions of at most GENERATION_RUN_CHUNK jobs each, so a book's run never
        holds the writer for long: a press waits for one chunk at most. A source taken by an
        operation since the choice sits the rest of the run out. A run that replaces what was
        made discards it as it chooses, so it chooses and queues in one write."""
        if replaces_results(cards):
            with self._unit_of_work.write():
                jobs, skipped = self._planned(scope, kind, cards, sort_order)
                queued = len(self._job_repo.enqueue(jobs))
        else:
            with self._unit_of_work.read():
                jobs, skipped = self._planned(scope, kind, cards, sort_order)
            queued = sum(
                self._queued(jobs[start:start + GENERATION_RUN_CHUNK])
                for start in range(0, len(jobs), GENERATION_RUN_CHUNK)
            )
        logger.info(
            "run_generation: queued (scope=%s, kind=%s, cards=%s, total=%d, skipped=%d,"
            " sort_order=%s)",
            scope.token, kind.value, cards.value, queued, skipped, sort_order.value,
        )
        return queued

    def _queued(self, jobs: list[Job]) -> int:
        """One chunk queued in its own write, but for the sources an operation holds now."""
        with self._unit_of_work.write():
            busy = {
                source_id for source_id in {job.source_id for job in jobs}
                if self._lock.held(source_id) is not None
            }
            return len(self._job_repo.enqueue([j for j in jobs if j.source_id not in busy]))

    def _planned(
        self,
        scope: SourceScope,
        kind: GenerationKind,
        cards: GenerationScope,
        sort_order: CandidateSortOrder,
    ) -> tuple[list[Job], int]:
        """The jobs of the run in the order chosen, and how many sources sit it out."""
        sources = self._scope_resolver.reviewable_sources(scope)
        chosen: list[tuple[GenerationTarget, GenerationCard]] = []
        skipped: list[DomainError] = []
        for source in sources:
            try:
                chosen.extend(self._chosen(source, kind, cards))
            except _SKIPPED as e:
                skipped.append(e)
        if skipped and len(skipped) == len(sources):
            raise skipped[0]

        target_of = {card.phrase_id: target for target, card in chosen}
        ordered = self._in_order(
            [card for _, card in chosen], sort_order, [s.id for s in sources if s.id is not None],
        )
        return [target_of[c.phrase_id].job(c) for c in ordered], len(skipped)

    def _chosen(
        self, source: Source, kind: GenerationKind, scope: GenerationScope,
    ) -> list[tuple[GenerationTarget, GenerationCard]]:
        """The source's cards to queue, by today's rules of one source."""
        assert source.id is not None
        source_id = source.id
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

        if replaces_results(scope):
            for card in chosen:
                target.discard(card)
            chosen = self._as_now(source_id, chosen)
        return [(target, card) for card in chosen]

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
