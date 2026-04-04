from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import StoredCandidateDTO
from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository


class GetCandidatesUseCase:
    """Retrieves candidates for a given source."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo

    def execute(self, source_id: int) -> list[StoredCandidateDTO]:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        candidates = self._candidate_repo.get_by_source(source_id)
        return [
            StoredCandidateDTO(
                id=c.id,  # type: ignore[arg-type]
                lemma=c.lemma,
                pos=c.pos,
                cefr_level=c.cefr_level,
                zipf_frequency=c.zipf_frequency,
                is_sweet_spot=c.is_sweet_spot,
                context_fragment=c.context_fragment,
                fragment_purity=c.fragment_purity,
                occurrences=c.occurrences,
                status=c.status.value,
            )
            for c in candidates
        ]
