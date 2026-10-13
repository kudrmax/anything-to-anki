from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import INITIALLY_SHOWN_CANDIDATES
from backend.application.dto.source_dtos import (
    SourceBoardDTO,
    SourceDetailDTO,
    SourceDTO,
    SourceGroupDTO,
    stored_candidate_to_dto,
)
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.source_stage import stage_of
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_stage import STAGE_ORDER

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.entities.source import Source
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.services.collection_tree import CollectionTree
    from backend.domain.value_objects.source_scope import SourceScope


class GetSourcesUseCase:
    """Retrieves sources (list and detail views)."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
        scope_resolver: SourceScopeResolver,
        generation_probe: TopicGenerationProbe,
        report_repo: CardReportRepository,
        anki_sync_repo: AnkiSyncRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._scope_resolver = scope_resolver
        self._generation_probe = generation_probe
        self._report_repo = report_repo
        self._anki_sync_repo = anki_sync_repo

    def list_all(self) -> list[SourceDTO]:
        tree = self._scope_resolver.tree()
        return [self._summary(s, tree) for s in self._source_repo.list_all()]

    def board(self, scope: SourceScope, query: str = "") -> SourceBoardDTO:
        tree = self._scope_resolver.tree()
        key = query.strip().casefold()
        sources = [
            s for s in self._scope_resolver.sources(scope)
            if not key or key in (s.title or "").casefold()
        ]
        summaries = [self._summary(s, tree) for s in sources]
        groups = [
            SourceGroupDTO(stage=stage.value, sources=[s for s in summaries if s.stage == stage])
            for stage in STAGE_ORDER
        ]
        return SourceBoardDTO(
            title=self._scope_resolver.title(scope),
            groups=[g for g in groups if g.sources],
        )

    def _summary(self, source: Source, tree: CollectionTree) -> SourceDTO:
        assert source.id is not None
        candidates = self._candidate_repo.get_by_source(source.id)
        generation = self._generation_probe.of(source)
        in_tree = source.collection_id is not None and tree.has(source.collection_id)
        return SourceDTO(
            id=source.id,
            title=source.title or "",
            status=source.status.value,
            stage=stage_of(source.status, awaiting_generation=generation.awaiting).value,
            kind=source.kind.value if source.kind else None,
            role=source.role.value,
            has_video=source.has_video,
            source_url=source.source_url,
            video_downloaded=source.video_path is not None,
            created_at=source.created_at,
            candidate_count=len(candidates),
            learn_count=sum(1 for c in candidates if c.status == CandidateStatus.LEARN),
            decided_count=sum(1 for c in candidates if c.status != CandidateStatus.PENDING),
            processing_stage=source.processing_stage.value if source.processing_stage else None,
            collection_id=source.collection_id,
            collection_path=tree.path(source.collection_id) if in_tree else [],  # type: ignore[arg-type]
            awaiting_generation=generation.awaiting,
            generation_status=generation.status,
            generation_error=generation.error,
            is_permanent=source.is_permanent,
        )

    def get_by_id(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> SourceDetailDTO:
        from backend.domain.services.candidate_sorting import decided_last

        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        assert source.id is not None
        candidates = self._candidate_repo.get_by_source(source.id)
        candidates = self._candidate_sorter.sort(candidates, source, sort_order)
        initially_shown = (
            None if sort_order == CandidateSortOrder.CHRONOLOGICAL
            else INITIALLY_SHOWN_CANDIDATES
        )
        candidates = decided_last(candidates)
        candidate_ids = [c.id for c in candidates if c.id is not None]
        jobs_by_candidate = self._job_repo.get_jobs_for_candidates(candidate_ids)
        reported_ids = self._report_repo.reported_candidate_ids(candidate_ids)
        synced_ids = self._anki_sync_repo.get_synced_candidate_ids(candidate_ids)
        return SourceDetailDTO(
            id=source.id,
            title=source.title or "",
            status=source.status.value,
            kind=source.kind.value if source.kind else None,
            role=source.role.value,
            has_video=source.has_video,
            can_polish_phrases=source.can_polish_phrases,
            has_source_text=source.has_text,
            source_url=source.source_url,
            video_downloaded=source.video_path is not None,
            error_message=source.error_message,
            processing_stage=source.processing_stage.value if source.processing_stage else None,
            created_at=source.created_at,
            candidates=[
                stored_candidate_to_dto(c, jobs_by_candidate, reported_ids, synced_ids)
                for c in candidates
            ],
            initially_shown_candidates=initially_shown,
        )
