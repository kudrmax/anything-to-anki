from __future__ import annotations

import collections
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.failed_error_group import FailedErrorGroup, SourceErrorCount
from backend.infrastructure.persistence.models import (
    CandidateMediaModel,
    SourceModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_media import CandidateMedia


class SqlaCandidateMediaRepository(CandidateMediaRepository):
    """SQLAlchemy implementation of CandidateMediaRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None:
        model = self._session.get(CandidateMediaModel, candidate_id)
        return model.to_entity() if model else None

    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]:
        stmt = (
            select(CandidateMediaModel)
            .join(
                StoredCandidateModel,
                StoredCandidateModel.id == CandidateMediaModel.candidate_id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]:
        stmt = (
            select(CandidateMediaModel)
            .join(
                StoredCandidateModel,
                StoredCandidateModel.id == CandidateMediaModel.candidate_id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [row.to_entity() for row in rows]

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMedia]:
        if not candidate_ids:
            return {}
        stmt = select(CandidateMediaModel).where(
            CandidateMediaModel.candidate_id.in_(candidate_ids)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def upsert(self, media: CandidateMedia) -> None:
        existing = self._session.get(CandidateMediaModel, media.candidate_id)
        if existing is None:
            self._session.add(CandidateMediaModel.from_entity(media))
        else:
            existing.screenshot_path = media.screenshot_path
            existing.audio_path = media.audio_path
            existing.start_ms = media.start_ms
            existing.end_ms = media.end_ms
            existing.status = media.status.value
            existing.error = media.error
            existing.generated_at = media.generated_at
        self._session.flush()

    def clear_paths(
        self,
        candidate_id: int,
        *,
        clear_screenshot: bool,
        clear_audio: bool,
    ) -> None:
        values: dict[str, None] = {}
        if clear_screenshot:
            values["screenshot_path"] = None
        if clear_audio:
            values["audio_path"] = None
        if not values:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id == candidate_id)
            .values(**values)
        )
        self._session.flush()

    def get_eligible_candidate_ids(
        self,
        source_id: int,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(
                CandidateMediaModel,
                CandidateMediaModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]
                ),
                CandidateMediaModel.start_ms.is_not(None),
                CandidateMediaModel.end_ms.is_not(None),
                CandidateMediaModel.screenshot_path.is_(None),
            )
        )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows]

    def mark_queued_bulk(self, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return
        existing_ids = set(
            self._session.execute(
                select(CandidateMediaModel.candidate_id).where(
                    CandidateMediaModel.candidate_id.in_(candidate_ids)
                )
            ).scalars().all()
        )
        for cid in candidate_ids:
            if cid in existing_ids:
                # Preserve timecodes and paths, only update status
                self._session.execute(
                    update(CandidateMediaModel)
                    .where(CandidateMediaModel.candidate_id == cid)
                    .values(status=EnrichmentStatus.QUEUED.value, error=None)
                )
            else:
                self._session.add(CandidateMediaModel(
                    candidate_id=cid,
                    screenshot_path=None,
                    audio_path=None,
                    start_ms=None,
                    end_ms=None,
                    status=EnrichmentStatus.QUEUED.value,
                    error=None,
                    generated_at=None,
                ))
        self._session.flush()

    def mark_running(self, candidate_id: int) -> None:
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id == candidate_id)
            .where(CandidateMediaModel.status.in_([
                EnrichmentStatus.QUEUED.value,
                EnrichmentStatus.IDLE.value,
            ]))
            .values(status=EnrichmentStatus.RUNNING.value)
        )
        self._session.flush()

    def mark_failed(self, candidate_id: int, error: str) -> None:
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id == candidate_id)
            .values(status=EnrichmentStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def mark_batch_failed(self, candidate_ids: list[int], error: str) -> None:
        if not candidate_ids:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id.in_(candidate_ids))
            .values(status=EnrichmentStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def mark_batch_cancelled(self, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return
        self._session.execute(
            update(CandidateMediaModel)
            .where(CandidateMediaModel.candidate_id.in_(candidate_ids))
            .values(status=EnrichmentStatus.CANCELLED.value, error="cancelled by user")
        )
        self._session.flush()

    def fail_all_running(self, error: str) -> int:
        count = self._session.query(CandidateMediaModel).filter(
            CandidateMediaModel.status == EnrichmentStatus.RUNNING.value,
        ).count()
        if count:
            self._session.execute(
                update(CandidateMediaModel)
                .where(CandidateMediaModel.status == EnrichmentStatus.RUNNING.value)
                .values(status=EnrichmentStatus.FAILED.value, error=error)
            )
            self._session.flush()
        return count

    def get_candidate_ids_by_status(
        self, source_id: int, status: EnrichmentStatus,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(
                CandidateMediaModel,
                CandidateMediaModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                CandidateMediaModel.status == status.value,
            )
        )
        return [row[0] for row in self._session.execute(stmt).all()]

    def count_by_status_global(
        self,
        status: EnrichmentStatus,
        source_id: int | None = None,
    ) -> int:
        stmt = (
            select(func.count(CandidateMediaModel.candidate_id))
            .join(StoredCandidateModel, StoredCandidateModel.id == CandidateMediaModel.candidate_id)
            .where(CandidateMediaModel.status == status.value)
        )
        if source_id is not None:
            stmt = stmt.where(StoredCandidateModel.source_id == source_id)
        return self._session.execute(stmt).scalar() or 0

    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
    ) -> list[FailedErrorGroup]:
        stmt = (
            select(
                CandidateMediaModel.candidate_id,
                CandidateMediaModel.error,
                StoredCandidateModel.source_id,
                SourceModel.title,
            )
            .join(StoredCandidateModel, StoredCandidateModel.id == CandidateMediaModel.candidate_id)
            .join(SourceModel, SourceModel.id == StoredCandidateModel.source_id)
            .where(CandidateMediaModel.status == EnrichmentStatus.FAILED.value)
        )
        if source_id is not None:
            stmt = stmt.where(StoredCandidateModel.source_id == source_id)
        rows = self._session.execute(stmt).all()

        error_candidate_ids: dict[str, list[int]] = collections.defaultdict(list)
        error_source_counts: dict[str, dict[int, tuple[str, int]]] = collections.defaultdict(dict)

        for candidate_id, error, src_id, src_title in rows:
            error_key = error or ""
            error_candidate_ids[error_key].append(candidate_id)
            if src_id not in error_source_counts[error_key]:
                error_source_counts[error_key][src_id] = (src_title or "", 0)
            title, count = error_source_counts[error_key][src_id]
            error_source_counts[error_key][src_id] = (title, count + 1)

        result: list[FailedErrorGroup] = []
        for error_text, candidate_ids in error_candidate_ids.items():
            source_counts = [
                SourceErrorCount(source_id=sid, source_title=title, count=cnt)
                for sid, (title, cnt) in error_source_counts[error_text].items()
            ]
            result.append(FailedErrorGroup(
                error_text=error_text,
                count=len(candidate_ids),
                source_counts=source_counts,
                candidate_ids=candidate_ids,
            ))
        return result

    def get_candidate_ids_by_error(
        self,
        error_text: str,
        source_id: int | None = None,
    ) -> list[int]:
        stmt = (
            select(CandidateMediaModel.candidate_id)
            .join(StoredCandidateModel, StoredCandidateModel.id == CandidateMediaModel.candidate_id)
            .where(
                CandidateMediaModel.status == EnrichmentStatus.FAILED.value,
                CandidateMediaModel.error == error_text,
            )
        )
        if source_id is not None:
            stmt = stmt.where(StoredCandidateModel.source_id == source_id)
        return [row[0] for row in self._session.execute(stmt).all()]
