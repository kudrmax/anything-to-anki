from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_USAGE_GROUP_ORDER
from backend.application.dto.source_dtos import (
    SourceDetailDTO,
    SourceDTO,
    stored_candidate_to_dto,
)
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

_PREVIEW_LENGTH: int = 100


class GetSourcesUseCase:
    """Retrieves sources (list and detail views)."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        job_repo: JobRepository,
        collection_repo: CollectionRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._job_repo = job_repo
        self._collection_repo = collection_repo

    def list_all(self, *, collection_id: int | None = None) -> list[SourceDTO]:
        sources = self._source_repo.list_all()
        if collection_id is not None:
            sources = [s for s in sources if s.collection_id == collection_id]

        # Build collection name map
        collections = self._collection_repo.list_all()
        coll_names: dict[int, str] = {
            c.id: c.name for c in collections if c.id is not None  # type: ignore[misc]
        }

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
                    collection_id=source.collection_id,
                    collection_name=(
                        coll_names.get(source.collection_id)
                        if source.collection_id
                        else None
                    ),
                )
            )
        return result

    def get_by_id(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> SourceDetailDTO:
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
        assert source.id is not None
        candidates = self._candidate_repo.get_by_source(source.id)
        if sort_order == SortEnum.CHRONOLOGICAL:
            text = source.cleaned_text or source.raw_text
            candidates = sort_chronologically(candidates, source_text=text)
        else:
            raw = self._settings_repo.get("usage_group_order")
            usage_order: list[str] = (
                json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
            )
            candidates = sort_by_relevance(candidates, usage_order=usage_order)
        candidate_ids = [c.id for c in candidates if c.id is not None]
        jobs_by_candidate = self._job_repo.get_jobs_for_candidates(candidate_ids)
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
            candidates=[
                stored_candidate_to_dto(c, jobs_by_candidate)
                for c in candidates
            ],
        )
