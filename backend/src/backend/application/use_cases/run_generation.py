from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.utils.generation_targets import job_of, target_for
from backend.domain.entities.job import Job
from backend.domain.exceptions import GenerationBlockedError, SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_generation_state import CardGenerationState
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.generation_targets import GenerationTarget
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.generation_kind import GenerationKind

logger = logging.getLogger(__name__)

# Cards already being generated are left alone in every scope: their job is about to
# deliver a fresh result anyway, and a second job would only duplicate the work.
_STATES_IN_SCOPE: dict[GenerationScope, frozenset[CardGenerationState]] = {
    GenerationScope.MISSING: frozenset({CardGenerationState.MISSING}),
    GenerationScope.FAILED: frozenset({CardGenerationState.FAILED}),
    GenerationScope.ALL: frozenset({
        CardGenerationState.DONE, CardGenerationState.FAILED, CardGenerationState.MISSING,
    }),
}


class RunGenerationUseCase:
    """Queues one kind of generation for the source's cards that fall into the scope."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        job_repo: JobRepository,
        candidate_sorter: CandidateSorter,
        targets: list[GenerationTarget],
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo
        self._candidate_sorter = candidate_sorter
        self._targets = targets

    def execute(
        self,
        source_id: int,
        kind: GenerationKind,
        scope: GenerationScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> int:
        """Returns how many cards were queued."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        target = target_for(self._targets, kind, source)
        video_downloading = self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.VIDEO_DOWNLOAD}),
        )
        blocker = target.blocker(source, video_downloading)
        if blocker is not None:
            raise GenerationBlockedError(source_id, blocker.value)

        candidates = [c for c in self._candidate_repo.get_by_source(source_id) if target.covers(c)]
        jobs = self._job_repo.get_jobs_for_candidates(
            [c.id for c in candidates if c.id is not None],
        )
        in_scope = _STATES_IN_SCOPE[scope]
        chosen = [c for c in candidates if target.state(c, job_of(jobs, c, kind)) in in_scope]

        if scope != GenerationScope.MISSING:
            self._job_repo.delete_failed_by_source_and_type(source_id, kind.job_type)
        if scope == GenerationScope.ALL:
            for candidate in chosen:
                assert candidate.id is not None
                target.discard(candidate.id)

        ordered = self._candidate_sorter.sort(chosen, source, sort_order)
        queued = self._queue(source_id, kind, ordered)
        logger.info(
            "run_generation: queued (source_id=%d, kind=%s, scope=%s, total=%d, sort_order=%s)",
            source_id, kind.value, scope.value, queued, sort_order.value,
        )
        return queued

    def _queue(
        self, source_id: int, kind: GenerationKind, candidates: list[StoredCandidate],
    ) -> int:
        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                id=None,
                job_type=kind.job_type,
                candidate_id=c.id,
                source_id=source_id,
                status=JobStatus.QUEUED,
                error=None,
                created_at=now,
                started_at=None,
            )
            for c in candidates
            if c.id is not None
        ]
        if jobs:
            self._job_repo.create_bulk(jobs)
        return len(jobs)
