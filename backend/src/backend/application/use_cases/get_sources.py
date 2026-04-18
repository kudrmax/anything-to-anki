from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO, breakdown_to_dto
from backend.application.dto.source_dtos import (
    CandidateMeaningDTO,
    CandidateMediaDTO,
    SourceDetailDTO,
    SourceDTO,
    StoredCandidateDTO,
)
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

_PREVIEW_LENGTH: int = 100


def _candidate_to_dto(c: StoredCandidate) -> StoredCandidateDTO:
    meaning_dto: CandidateMeaningDTO | None = None
    if c.meaning is not None:
        meaning_dto = CandidateMeaningDTO(
            meaning=c.meaning.meaning,
            translation=c.meaning.translation,
            synonyms=c.meaning.synonyms,
            examples=c.meaning.examples,
            ipa=c.meaning.ipa,
            status=c.meaning.status.value,
            error=c.meaning.error,
            generated_at=c.meaning.generated_at,
        )
    media_dto: CandidateMediaDTO | None = None
    if c.media is not None:
        media_dto = CandidateMediaDTO(
            screenshot_path=c.media.screenshot_path,
            audio_path=c.media.audio_path,
            start_ms=c.media.start_ms,
            end_ms=c.media.end_ms,
            status=c.media.status.value,
            error=c.media.error,
            generated_at=c.media.generated_at,
        )
    breakdown_dto: CEFRBreakdownDTO | None = None
    if c.cefr_breakdown is not None:
        breakdown_dto = breakdown_to_dto(c.cefr_breakdown)
    return StoredCandidateDTO(
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
        is_phrasal_verb=c.is_phrasal_verb,
        meaning=meaning_dto,
        media=media_dto,
        cefr_breakdown=breakdown_dto,
    )


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
                    source_type=source.input_method.value,
                    content_type=source.content_type.value,
                    source_url=source.source_url,
                    video_downloaded=source.video_path is not None,
                    created_at=source.created_at,
                    candidate_count=len(candidates),
                    learn_count=learn_count,
                    processing_stage=(
                        source.processing_stage.value if source.processing_stage else None
                    ),
                )
            )
        return result

    def get_by_id(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> SourceDetailDTO:
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        assert source.id is not None
        if sort_order == SortEnum.CHRONOLOGICAL:
            candidates = self._candidate_repo.get_by_source(source.id)
            text = source.cleaned_text or source.raw_text
            candidates.sort(
                key=lambda c: (text.find(c.context_fragment), c.id or 0),
            )
        else:
            candidates = self._candidate_repo.get_by_source(source.id, sort_order=sort_order)
        return SourceDetailDTO(
            id=source.id,
            title=source.title or source.raw_text[:_PREVIEW_LENGTH],
            raw_text=source.raw_text,
            cleaned_text=source.cleaned_text,
            status=source.status.value,
            source_type=source.input_method.value,
            content_type=source.content_type.value,
            source_url=source.source_url,
            video_downloaded=source.video_path is not None,
            error_message=source.error_message,
            processing_stage=source.processing_stage.value if source.processing_stage else None,
            created_at=source.created_at,
            candidates=[_candidate_to_dto(c) for c in candidates],
        )
