from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from backend.application.dto.generation_dtos import GenerationKindStatusDTO, GenerationStatusDTO
from backend.application.utils.generation_targets import job_of
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.generation_targets import GenerationTarget
    from backend.domain.entities.job import Job
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class GetGenerationStatusUseCase:
    """How far every kind of background generation got for a source's cards."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        job_repo: JobRepository,
        targets: list[GenerationTarget],
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo
        self._targets = targets

    def execute(self, source_id: int) -> GenerationStatusDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        candidates = self._candidate_repo.get_by_source(source_id)
        jobs = self._job_repo.get_jobs_for_candidates(
            [c.id for c in candidates if c.id is not None],
        )
        video_downloading = self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.VIDEO_DOWNLOAD}),
        )
        kinds = [
            self._kind_status(target, source, candidates, jobs, video_downloading)
            for target in self._targets
            if target.applies_to(source)
        ]
        return GenerationStatusDTO(
            kinds=kinds,
            in_progress=video_downloading or any(k.running > 0 for k in kinds),
        )

    @staticmethod
    def _kind_status(
        target: GenerationTarget,
        source: Source,
        candidates: list[StoredCandidate],
        jobs: dict[int, dict[str, Job]],
        video_downloading: bool,
    ) -> GenerationKindStatusDTO:
        states = Counter(
            target.state(c, job_of(jobs, c, target.kind))
            for c in candidates
            if target.covers(c)
        )
        return GenerationKindStatusDTO(
            kind=target.kind,
            total=states.total(),
            done=states[CardGenerationState.DONE],
            running=states[CardGenerationState.RUNNING],
            failed=states[CardGenerationState.FAILED],
            missing=states[CardGenerationState.MISSING],
            blocked_by=target.blocker(source, video_downloading),
        )
