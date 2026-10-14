from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import CardJobs, card_to_dto
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.candidate_sorter import ArrangedCards, CandidateSorter
    from backend.application.utils.review_cards import ReviewCards
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.review_card import ReviewCard


@dataclass(frozen=True)
class CardListing:
    """The cards of a source in review order, and how far the user got with them."""

    cards: list[CardDTO]
    progress: DecisionProgress


class CardViews:
    """Cards as the API shows them: with the jobs of their phrases and words, and whether
    the user reported them."""

    def __init__(
        self,
        review_cards: ReviewCards,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
        report_repo: CardReportRepository,
    ) -> None:
        self._review_cards = review_cards
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._report_repo = report_repo

    def listed(
        self, source_id: int, order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> CardListing:
        arranged = self._candidate_sorter.arrange(self._review_cards.of_source(source_id), order)
        return CardListing(cards=self._dtos(arranged), progress=arranged.progress())

    def one(self, phrase_id: int) -> CardDTO:
        """The card of the phrase, as an answer to an action on it."""
        card = self._review_cards.of_phrase(phrase_id)
        if card is None:
            raise PhraseNotFoundError(phrase_id)
        jobs = self._jobs([card])
        reported = self._report_repo.reported_phrase_ids([phrase_id])
        return card_to_dto(card, jobs, reported=phrase_id in reported)

    def _dtos(self, arranged: ArrangedCards) -> list[CardDTO]:
        jobs = self._jobs(arranged.cards)
        reported = self._report_repo.reported_phrase_ids([c.phrase_id for c in arranged.cards])
        return [
            card_to_dto(
                card, jobs, reported=card.phrase_id in reported, section=arranged.section(card),
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
