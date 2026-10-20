from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import CardJobs, CardSourceDTO, card_to_dto
from backend.domain.exceptions import PhraseNotFoundError, SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.candidate_sorter import ArrangedCards, CandidateSorter
    from backend.application.utils.review_cards import ReviewCards
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.held_operation import HeldOperation
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.source_scope import SourceScope


@dataclass(frozen=True)
class CardListing:
    """The cards of a set of sources in review order, how far the user got with them, the
    sources in the set's order and the operations holding sources when the cards were read."""

    cards: list[CardDTO]
    progress: DecisionProgress
    sources: list[Source]
    operations: Mapping[int, HeldOperation]


class CardViews:
    """Cards as the API shows them: with their source, the jobs of their phrases and words,
    and whether the user reported them."""

    def __init__(
        self,
        review_cards: ReviewCards,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
        report_repo: CardReportRepository,
        scope_resolver: SourceScopeResolver,
        source_repo: SourceRepository,
        lock: SourceOperationLock,
    ) -> None:
        self._review_cards = review_cards
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._report_repo = report_repo
        self._scope_resolver = scope_resolver
        self._source_repo = source_repo
        self._lock = lock

    def listed(
        self, scope: SourceScope, order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> CardListing:
        sources = self._scope_resolver.reviewable_sources(scope)
        source_ids = [s.id for s in sources if s.id is not None]
        arranged = self._candidate_sorter.arrange(
            self._review_cards.of_sources(source_ids), order, source_order=source_ids,
        )
        operations = self._lock.operations()
        return CardListing(
            cards=self._dtos(arranged, _source_dtos(sources, operations)),
            progress=arranged.progress(),
            sources=sources,
            operations=operations,
        )

    def one(self, phrase_id: int) -> CardDTO:
        """The card of the phrase, as an answer to an action on it, with its section."""
        card = self._review_cards.of_phrase(phrase_id)
        if card is None:
            raise PhraseNotFoundError(phrase_id)
        source_id = card.word.source_id
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        jobs = self._jobs([card])
        reported = self._report_repo.reported_phrase_ids([phrase_id])
        return card_to_dto(
            card, _source_dto(source, self._lock.operations()), jobs,
            reported=phrase_id in reported,
            section=self._candidate_sorter.section(card),
        )

    def _dtos(
        self, arranged: ArrangedCards, sources: dict[int, CardSourceDTO],
    ) -> list[CardDTO]:
        jobs = self._jobs(arranged.cards)
        reported = self._report_repo.reported_phrase_ids([c.phrase_id for c in arranged.cards])
        return [
            card_to_dto(
                card, sources[card.word.source_id], jobs,
                reported=card.phrase_id in reported, section=arranged.section(card),
            )
            for card in arranged.cards
        ]

    def _jobs(self, cards: list[ReviewCard]) -> CardJobs:
        return CardJobs(
            of_phrases=self._job_repo.get_jobs_for_phrases([c.phrase_id for c in cards]),
            of_words=self._job_repo.get_jobs_for_candidates(
                list(dict.fromkeys(c.word_id for c in cards)),
            ),
        )


def _source_dto(source: Source, operations: Mapping[int, HeldOperation]) -> CardSourceDTO:
    assert source.id is not None
    operation = operations.get(source.id)
    return CardSourceDTO.of(source, operation.kind if operation is not None else None)


def _source_dtos(
    sources: list[Source], operations: Mapping[int, HeldOperation],
) -> dict[int, CardSourceDTO]:
    return {s.id: _source_dto(s, operations) for s in sources if s.id is not None}
