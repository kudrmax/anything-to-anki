from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import PhrasePolishNotSupportedError, SourceNotFoundError
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository


class EnqueuePhrasePolishUseCase:
    """Queues AI polishing of one phrase again; whole sources go through RunGeneration."""

    def __init__(
        self,
        cards: RequestedCards,
        occurrence_repo: OccurrenceRepository,
        source_repo: SourceRepository,
        job_repo: JobRepository,
    ) -> None:
        self._cards = cards
        self._occurrence_repo = occurrence_repo
        self._source_repo = source_repo
        self._job_repo = job_repo

    def execute(self, phrase_id: int) -> None:
        """Polish the phrase again from its source text."""
        card = self._cards.card(phrase_id)
        source_id = card.word.source_id
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if not source.can_polish_phrases:
            raise PhrasePolishNotSupportedError(source_id)
        self._occurrence_repo.write_text(
            card.phrase_id, card.phrase.source_phrase, card.phrase.phrase_position,
            polished=None,
        )
        written = self._occurrence_repo.get(card.phrase_id)
        assert written is not None
        self._job_repo.enqueue([Job.queued(
            JobType.POLISH, source_id, card.word_id,
            phrase_id=card.phrase_id, phrase_revision=written.revision,
        )])
