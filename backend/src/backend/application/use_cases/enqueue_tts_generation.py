from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_USAGE_GROUP_ORDER
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.settings_repository import SettingsRepository


class EnqueueTTSGenerationUseCase:
    """Finds eligible candidates, creates JobType.TTS jobs."""

    def __init__(
        self,
        tts_repo: CandidateTTSRepository,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        job_repo: JobRepository,
    ) -> None:
        self._tts_repo = tts_repo
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._job_repo = job_repo

    def execute(self, source_id: int) -> list[int]:
        from backend.domain.services.candidate_sorting import sort_by_relevance

        unsorted_ids = self._tts_repo.get_eligible_candidate_ids(source_id)
        if not unsorted_ids:
            return []

        candidates = self._candidate_repo.get_by_ids(unsorted_ids)
        raw = self._settings_repo.get("usage_group_order")
        usage_order: list[str] = json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
        sorted_candidates = sort_by_relevance(candidates, usage_order=usage_order)

        eligible_ids = [c.id for c in sorted_candidates if c.id is not None]
        if not eligible_ids:
            return []

        now = datetime.now(tz=UTC)
        jobs = [
            Job(
                id=None,
                job_type=JobType.TTS,
                candidate_id=cid,
                source_id=source_id,
                status=JobStatus.QUEUED,
                error=None,
                created_at=now,
                started_at=None,
            )
            for cid in eligible_ids
        ]
        self._job_repo.create_bulk(jobs)

        logger.info(
            "enqueue_tts_generation: queued (source_id=%d, count=%d)",
            source_id, len(eligible_ids),
        )
        return eligible_ids
