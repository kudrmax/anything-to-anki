from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.use_cases.meaning_follow_up import check_follow_up
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp


class EnqueuePhraseMeaningUseCase:
    """Queues the meaning of one phrase, or a follow-up about it; the worker calls the AI."""

    def __init__(self, cards: RequestedCards, job_repo: JobRepository) -> None:
        self._cards = cards
        self._job_repo = job_repo

    def execute(self, phrase_id: int, follow_up: MeaningFollowUp | None = None) -> None:
        if follow_up is not None:
            check_follow_up(follow_up)
        card = self._cards.card(phrase_id)
        job_type = JobType.MEANING if follow_up is None else JobType.MEANING_FOLLOW_UP
        self._job_repo.enqueue([Job.queued(
            job_type, card.word.source_id, card.word_id,
            phrase_id=card.phrase_id, phrase_revision=card.phrase.revision,
            follow_up=follow_up,
        )])
