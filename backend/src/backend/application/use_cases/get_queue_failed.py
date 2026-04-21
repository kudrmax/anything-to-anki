from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import (
    FailedByJobTypeDTO,
    FailedGroupDTO,
    FailedSourceDTO,
    QueueFailedDTO,
)

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import (
        CandidateMeaningRepository,
    )
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_pronunciation_repository import (
        CandidatePronunciationRepository,
    )


class GetQueueFailedUseCase:
    """Return failed enrichments grouped by job type → error text."""

    def __init__(
        self,
        meaning_repo: CandidateMeaningRepository,
        media_repo: CandidateMediaRepository,
        pronunciation_repo: CandidatePronunciationRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._media_repo = media_repo
        self._pronunciation_repo = pronunciation_repo

    def execute(self, source_id: int | None = None) -> QueueFailedDTO:
        types: list[FailedByJobTypeDTO] = []
        for job_type, repo in [
            ("meanings", self._meaning_repo),
            ("media", self._media_repo),
            ("pronunciation", self._pronunciation_repo),
        ]:
            groups_raw = repo.get_failed_grouped_by_error(
                source_id=source_id,
            )
            if not groups_raw:
                continue

            groups = [
                FailedGroupDTO(
                    error_text=g.error_text,
                    count=g.count,
                    sources=[
                        FailedSourceDTO(
                            source_id=s.source_id,
                            source_title=s.source_title,
                            count=s.count,
                        )
                        for s in g.source_counts
                    ],
                    candidate_ids=g.candidate_ids,
                )
                for g in groups_raw
            ]
            total_failed = sum(g.count for g in groups_raw)
            types.append(
                FailedByJobTypeDTO(
                    job_type=job_type,
                    total_failed=total_failed,
                    groups=groups,
                )
            )

        return QueueFailedDTO(types=types)
