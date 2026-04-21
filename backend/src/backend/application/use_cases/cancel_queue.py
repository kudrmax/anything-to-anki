from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import (
        CandidateMeaningRepository,
    )
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )
    from backend.domain.ports.queue_inspector import QueueInspectorPort

_EnrichmentRepo = Union[
    "CandidateMeaningRepository",
    "CandidateMediaRepository",
    "CandidatePronunciationRepository",
]

_VALID_JOB_TYPES = frozenset({"meanings", "media", "pronunciation"})


class CancelQueueUseCase:
    """Cancel queued jobs by type or by a specific job_id."""

    def __init__(
        self,
        inspector: QueueInspectorPort,
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
    ) -> None:
        self._inspector = inspector
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo

    def _validate_job_type(self, job_type: str) -> None:
        if job_type not in _VALID_JOB_TYPES:
            raise ValueError(f"Unknown job_type: {job_type!r}")

    async def execute(
        self,
        job_type: str,
        source_id: int | None = None,
        job_id: str | None = None,
    ) -> int:
        self._validate_job_type(job_type)

        if job_id is not None:
            cancelled = await self._inspector.cancel_job(job_id)
            return 1 if cancelled else 0

        return await self._inspector.cancel_jobs_by_type(
            job_type, source_id=source_id
        )
