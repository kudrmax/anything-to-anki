from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import SourceDetailDTO, SourceDTO, StoredCandidateDTO
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository

_PREVIEW_LENGTH: int = 100


class GetSourcesUseCase:
    """Retrieves sources (list and detail views)."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo

    def list_all(self) -> list[SourceDTO]:
        sources = self._source_repo.list_all()
        result: list[SourceDTO] = []
        for source in sources:
            assert source.id is not None
            candidates = self._candidate_repo.get_by_source(source.id)
            learn_count = sum(1 for c in candidates if c.status == CandidateStatus.LEARN)
            result.append(
                SourceDTO(
                    id=source.id,
                    title=source.title or source.raw_text[:_PREVIEW_LENGTH],
                    raw_text_preview=source.raw_text[:_PREVIEW_LENGTH],
                    status=source.status.value,
                    source_type=source.source_type.value,
                    created_at=source.created_at,
                    candidate_count=len(candidates),
                    learn_count=learn_count,
                    processing_stage=source.processing_stage.value if source.processing_stage else None,
                )
            )
        return result

    def get_by_id(self, source_id: int) -> SourceDetailDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        assert source.id is not None
        candidates = self._candidate_repo.get_by_source(source.id)
        return SourceDetailDTO(
            id=source.id,
            title=source.title or source.raw_text[:_PREVIEW_LENGTH],
            raw_text=source.raw_text,
            cleaned_text=source.cleaned_text,
            status=source.status.value,
            source_type=source.source_type.value,
            error_message=source.error_message,
            processing_stage=source.processing_stage.value if source.processing_stage else None,
            created_at=source.created_at,
            candidates=[
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
                    surface_form=c.surface_form,
                    meaning=c.meaning,
                    ipa=c.ipa,
                    is_phrasal_verb=c.is_phrasal_verb,
                )
                for c in candidates
            ],
        )
