from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.job_repository import JobRepository


class EnqueuePhraseTTSUseCase:
    """Queues TTS for one phrase; a phrase already waiting for TTS is not queued twice."""

    def __init__(self, cards: RequestedCards, job_repo: JobRepository) -> None:
        self._cards = cards
        self._job_repo = job_repo

    def execute(self, phrase_id: int) -> None:
        card = self._cards.card(phrase_id)
        self._job_repo.enqueue([Job.queued(
            JobType.TTS, card.word.source_id, card.word_id,
            phrase_id=card.phrase_id, phrase_revision=card.phrase.revision,
        )])
