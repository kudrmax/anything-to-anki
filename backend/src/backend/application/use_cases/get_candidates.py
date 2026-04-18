from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO, breakdown_to_dto
from backend.application.dto.source_dtos import (
    CandidateMeaningDTO,
    CandidateMediaDTO,
    StoredCandidateDTO,
)
from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


def _to_dto(c: StoredCandidate) -> StoredCandidateDTO:
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
        surface_form=c.surface_form,
        is_phrasal_verb=c.is_phrasal_verb,
        status=c.status.value,
        meaning=meaning_dto,
        media=media_dto,
        cefr_breakdown=breakdown_dto,
    )


class GetCandidatesUseCase:
    """Retrieves candidates for a given source."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[StoredCandidateDTO]:
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if sort_order == SortEnum.CHRONOLOGICAL:
            # Python sort by position of context_fragment in source text — SQL
            # cannot do this without custom functions, and it's only N substring
            # scans for a few hundred candidates.
            candidates = self._candidate_repo.get_by_source(source_id)
            text = source.cleaned_text or source.raw_text
            candidates.sort(
                key=lambda c: (text.find(c.context_fragment), c.id or 0),
            )
        else:
            candidates = self._candidate_repo.get_by_source(source_id, sort_order=sort_order)
        return [_to_dto(c) for c in candidates]
