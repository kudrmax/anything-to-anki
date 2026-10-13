from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.constants import INITIALLY_SHOWN_CANDIDATES
from backend.application.dto.source_dtos import (
    SourceDetailDTO,
    SourceDTO,
    stored_candidate_to_dto,
)
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_role import SourceRole

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.entities.source import Source
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.card_report_repository import CardReportRepository
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository

_PENDING_JOB_STATUSES = [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.FAILED]


@dataclass(frozen=True)
class _TopicGeneration:
    """AI step of a topic source: whether it is still needed and how its job is doing."""

    awaiting: bool = False
    status: str | None = None
    error: str | None = None


class GetSourcesUseCase:
    """Retrieves sources (list and detail views)."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        candidate_sorter: CandidateSorter,
        job_repo: JobRepository,
        collection_repo: CollectionRepository,
        topic_target_repo: TopicTargetRepository,
        report_repo: CardReportRepository,
        anki_sync_repo: AnkiSyncRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._candidate_sorter = candidate_sorter
        self._job_repo = job_repo
        self._collection_repo = collection_repo
        self._topic_target_repo = topic_target_repo
        self._report_repo = report_repo
        self._anki_sync_repo = anki_sync_repo

    def list_all(self, *, collection_id: int | None = None) -> list[SourceDTO]:
        sources = self._source_repo.list_all()
        if collection_id is not None:
            sources = [s for s in sources if s.collection_id == collection_id]

        # Build collection name map
        collections = self._collection_repo.list_all()
        coll_names: dict[int, str] = {
            c.id: c.name for c in collections if c.id is not None
        }

        result: list[SourceDTO] = []
        for source in sources:
            assert source.id is not None
            candidates = self._candidate_repo.get_by_source(source.id)
            learn_count = sum(1 for c in candidates if c.status == CandidateStatus.LEARN)
            ready = self._candidate_sorter.arrange(candidates).ready()
            generation = self._generation_of(source)
            result.append(
                SourceDTO(
                    id=source.id,
                    title=source.title or "",
                    status=source.status.value,
                    kind=source.kind.value if source.kind else None,
                    role=source.role.value,
                    has_video=source.has_video,
                    source_url=source.source_url,
                    video_downloaded=source.video_path is not None,
                    created_at=source.created_at,
                    candidate_count=len(candidates),
                    learn_count=learn_count,
                    ready_count=len(ready),
                    ready_decided_count=sum(
                        1 for c in ready if c.status != CandidateStatus.PENDING
                    ),
                    processing_stage=(
                        source.processing_stage.value if source.processing_stage else None
                    ),
                    collection_id=source.collection_id,
                    collection_name=(
                        coll_names.get(source.collection_id)
                        if source.collection_id
                        else None
                    ),
                    awaiting_generation=generation.awaiting,
                    generation_status=generation.status,
                    generation_error=generation.error,
                    is_permanent=source.is_permanent,
                )
            )
        return result

    def _generation_of(self, source: Source) -> _TopicGeneration:
        assert source.id is not None
        if source.role is not SourceRole.TOPIC or self._topic_target_repo.has_targets(
            source.id,
        ):
            return _TopicGeneration()
        jobs = self._job_repo.get_jobs_by_status(
            _PENDING_JOB_STATUSES, source_id=source.id, job_type=JobType.TOPIC_TARGETS,
        )
        job = jobs[0] if jobs else None
        return _TopicGeneration(
            awaiting=True,
            status=job.status.value if job else None,
            error=job.error if job else None,
        )

    def get_by_id(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> SourceDetailDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        assert source.id is not None
        arranged = self._candidate_sorter.arrange(
            self._candidate_repo.get_by_source(source.id), sort_order,
        )
        candidates = arranged.candidates
        ready = arranged.ready()
        initially_shown = (
            None if sort_order == CandidateSortOrder.CHRONOLOGICAL
            else INITIALLY_SHOWN_CANDIDATES
        )
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
                stored_candidate_to_dto(
                    c, jobs_by_candidate, reported_ids, synced_ids, arranged.section(c),
                )
                for c in candidates
            ],
            ready_total=len(ready),
            ready_reviewed=sum(1 for c in ready if c.status != CandidateStatus.PENDING),
            initially_shown_candidates=initially_shown,
        )
