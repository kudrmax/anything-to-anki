from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import CardJobs, CardSourceDTO, card_to_dto
from backend.domain.exceptions import PhraseNotFoundError, SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.candidate_sorter import ArrangedCards, CandidateSorter
    from backend.application.utils.review_cards import ReviewCards
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.source_scope import SourceScope


@dataclass(frozen=True)
class CardListing:
    """The cards of a set of sources in review order, how far the user got with them and the
    sources in the set's order."""

    cards: list[CardDTO]
    progress: DecisionProgress
    sources: list[Source]


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
    ) -> None:
        self._review_cards = review_cards
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._report_repo = report_repo
        self._scope_resolver = scope_resolver
        self._source_repo = source_repo

    def listed(
        self, scope: SourceScope, order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> CardListing:
        sources = self._scope_resolver.reviewable_sources(scope)
        source_ids = [s.id for s in sources if s.id is not None]
        arranged = self._candidate_sorter.arrange(
            self._review_cards.of_sources(source_ids), order, source_order=source_ids,
        )
        return CardListing(
            cards=self._dtos(
                arranged, {s.id: CardSourceDTO.of(s) for s in sources if s.id is not None},
            ),
            progress=arranged.progress(),
            sources=sources,
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
            card, CardSourceDTO.of(source), jobs,
            reported=phrase_id in reported,
            section=self._candidate_sorter.section(card),
        )

    def of_phrases(
        self, phrase_ids: Sequence[int], sections: Mapping[int, CandidateSection],
    ) -> list[CardDTO]:
        """The cards of these phrases in the order given, each in the section `sections`
        gives it; a phrase that is gone is left out. Read for exactly these phrases."""
        cards = self._review_cards.of_phrases(phrase_ids)
        sources: dict[int, CardSourceDTO] = {}
        for source_id in dict.fromkeys(card.source_id for card in cards):
            source = self._source_repo.get_by_id(source_id)
            if source is None:
                raise SourceNotFoundError(source_id)
            sources[source_id] = CardSourceDTO.of(source)
        jobs = self._jobs(cards)
        reported = self._report_repo.reported_phrase_ids([c.phrase_id for c in cards])
        return [
            card_to_dto(
                card, sources[card.source_id], jobs,
                reported=card.phrase_id in reported, section=sections[card.phrase_id],
            )
            for card in cards
        ]

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

