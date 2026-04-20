from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_USAGE_GROUP_ORDER
from backend.application.dto.cefr_dtos import CEFRBreakdownDTO, breakdown_to_dto
from backend.application.dto.source_dtos import (
    CandidateMeaningDTO,
    CandidateMediaDTO,
    CandidatePronunciationDTO,
    StoredCandidateDTO,
)
from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
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
    pronunciation_dto: CandidatePronunciationDTO | None = None
    if c.pronunciation is not None:
        pronunciation_dto = CandidatePronunciationDTO(
            us_audio_path=c.pronunciation.us_audio_path,
            uk_audio_path=c.pronunciation.uk_audio_path,
            status=c.pronunciation.status.value,
            error=c.pronunciation.error,
            generated_at=c.pronunciation.generated_at,
        )

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
        pronunciation=pronunciation_dto,
        cefr_breakdown=breakdown_dto,
        usage_distribution=c.usage_distribution.to_dict() if c.usage_distribution else None,
    )


class GetCandidatesUseCase:
    """Retrieves candidates for a given source."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[StoredCandidateDTO]:
        from backend.domain.services.candidate_sorting import (
            sort_by_relevance,
            sort_chronologically,
        )
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        candidates = self._candidate_repo.get_by_source(source_id)
        if sort_order == SortEnum.CHRONOLOGICAL:
            text = source.cleaned_text or source.raw_text
            candidates = sort_chronologically(candidates, source_text=text)
        else:
            raw = self._settings_repo.get("usage_group_order")
            usage_order: list[str] = (
                json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
            )
            candidates = sort_by_relevance(candidates, usage_order=usage_order)
        return [_to_dto(c) for c in candidates]
