from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import (
    FailedByJobTypeDTO,
    FailedGroupDTO,
    FailedSourceDTO,
    QueueFailedDTO,
)

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class GetQueueFailedUseCase:
    """Return failed jobs grouped by job type -> error text."""

    def __init__(
        self,
        job_repo: JobRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._job_repo = job_repo
        self._source_repo = source_repo

    def execute(self, source_id: int | None = None) -> QueueFailedDTO:
        raw_groups = self._job_repo.get_failed_grouped_by_error(source_id=source_id)
        if not raw_groups:
            return QueueFailedDTO(types=[])

        # Collect all source IDs for title lookup
        all_source_ids: set[int] = set()
        for g in raw_groups:
            all_source_ids.update(g["source_ids"])
        title_map = self._source_repo.get_title_map(list(all_source_ids)) if all_source_ids else {}

        # Group by job_type
        by_type: dict[str, list[FailedGroupDTO]] = {}
        for g in raw_groups:
            jt: str = g["job_type"]
            group_dto = FailedGroupDTO(
                error_text=g["error"],
                count=g["count"],
                sources=[
                    FailedSourceDTO(
                        source_id=sid,
                        source_title=title_map.get(sid, ""),
                        count=0,
                    )
                    for sid in g["source_ids"]
                ],
                candidate_ids=g["candidate_ids"],
            )
            by_type.setdefault(jt, []).append(group_dto)

        types = [
            FailedByJobTypeDTO(
                job_type=jt,
                total_failed=sum(g.count for g in groups),
                groups=groups,
            )
            for jt, groups in by_type.items()
        ]

        return QueueFailedDTO(types=types)
