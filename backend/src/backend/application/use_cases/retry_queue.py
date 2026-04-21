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

_EnrichmentRepo = Union[
    "CandidateMeaningRepository",
    "CandidateMediaRepository",
    "CandidatePronunciationRepository",
]

_VALID_JOB_TYPES = frozenset({"meanings", "media", "pronunciation"})


class RetryQueueUseCase:
    """Re-queue failed enrichments for the given job type."""

    def __init__(
        self,
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo

    def _repo_for(self, job_type: str) -> _EnrichmentRepo:
        if job_type == "meanings":
            return self._meaning_repo
        if job_type == "media":
            return self._media_repo
        if job_type == "pronunciation":
            return self._pronunciation_repo
        raise ValueError(f"Unknown job_type: {job_type!r}")

    def execute(
        self,
        job_type: str,
        source_id: int | None = None,
        error_text: str | None = None,
    ) -> int:
        repo = self._repo_for(job_type)

        if error_text is not None:
            candidate_ids = repo.get_candidate_ids_by_error(
                error_text, source_id=source_id
            )
        else:
            groups = repo.get_failed_grouped_by_error(source_id=source_id)
            candidate_ids = [cid for g in groups for cid in g.candidate_ids]

        if not candidate_ids:
            return 0

        repo.mark_queued_bulk(candidate_ids)
        return len(candidate_ids)
