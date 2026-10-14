from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import GenerationCard
from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import PhraseNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock


class RequestedCards:
    """The card the user asked to generate something for, while its source is free."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        lock: SourceOperationLock,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._lock = lock

    def card(self, phrase_id: int) -> GenerationCard:
        """Raises PhraseNotFoundError, or SourceOperationBusyError during a long operation."""
        phrase = self._occurrence_repo.get(phrase_id)
        word = (
            self._candidate_repo.get_by_id(phrase.candidate_id) if phrase is not None else None
        )
        if phrase is None or word is None:
            raise PhraseNotFoundError(phrase_id)
        ensure_source_free(self._lock, word.source_id)
        return GenerationCard(word, phrase)
