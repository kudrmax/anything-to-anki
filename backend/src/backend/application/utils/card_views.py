from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import CardJobs, CardSourceDTO, card_to_dto
from backend.domain.exceptions import PhraseNotFoundError, SourceNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.review_cards import ReviewCards
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.review_card import ReviewCard


class CardViews:
    """Cards as the API shows them: with their source, the jobs of their phrases and words,
    and whether the user reported them."""

    def __init__(
        self,
        review_cards: ReviewCards,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
        report_repo: CardReportRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._review_cards = review_cards
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._report_repo = report_repo
        self._source_repo = source_repo

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
            usage_order=self._candidate_sorter.usage_order(),
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
        usage_order = self._candidate_sorter.usage_order()
        return [
            card_to_dto(
                card, sources[card.source_id], jobs,
                reported=card.phrase_id in reported, section=sections[card.phrase_id],
                usage_order=usage_order,
            )
            for card in cards
        ]

    def _jobs(self, cards: list[ReviewCard]) -> CardJobs:
        return CardJobs(
            of_phrases=self._job_repo.get_jobs_for_phrases([c.phrase_id for c in cards]),
            of_words=self._job_repo.get_jobs_for_candidates(
                list(dict.fromkeys(c.word_id for c in cards)),
            ),
        )

