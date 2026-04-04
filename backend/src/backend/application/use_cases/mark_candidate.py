from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository


class MarkCandidateUseCase:
    """Marks a candidate status and optionally adds to known words."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo

    def execute(self, candidate_id: int, status: CandidateStatus) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        self._candidate_repo.update_status(candidate_id, status)
        if status == CandidateStatus.KNOWN:
            self._known_word_repo.add(candidate.lemma, candidate.pos)
