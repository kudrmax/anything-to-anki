from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceIsProcessingError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository


class DeleteSourceUseCase:
    """Deletes a source and all its candidates."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status == SourceStatus.PROCESSING:
            raise SourceIsProcessingError(source_id)
        self._candidate_repo.delete_by_source(source_id)
        self._source_repo.delete(source_id)
