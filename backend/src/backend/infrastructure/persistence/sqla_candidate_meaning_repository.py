from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select, update

from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_meaning import CandidateMeaning


class SqlaCandidateMeaningRepository(CandidateMeaningRepository):
    """SQLAlchemy implementation of CandidateMeaningRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaning | None:
        model = self._session.get(CandidateMeaningModel, candidate_id)
        return model.to_entity() if model else None

    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMeaning]:
        # Join through candidates table to filter by source_id
        stmt = (
            select(CandidateMeaningModel)
            .join(
                StoredCandidateModel,
                StoredCandidateModel.id == CandidateMeaningModel.candidate_id,
            )
            .where(StoredCandidateModel.source_id == source_id)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMeaning]:
        if not candidate_ids:
            return {}
        stmt = select(CandidateMeaningModel).where(
            CandidateMeaningModel.candidate_id.in_(candidate_ids)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def upsert(self, meaning: CandidateMeaning) -> None:
        existing = self._session.get(CandidateMeaningModel, meaning.candidate_id)
        if existing is None:
            self._session.add(CandidateMeaningModel.from_entity(meaning))
        else:
            existing.meaning = meaning.meaning
            existing.ipa = meaning.ipa
            existing.status = meaning.status.value
            existing.error = meaning.error
            existing.generated_at = meaning.generated_at
        self._session.flush()

    def get_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .outerjoin(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                or_(
                    CandidateMeaningModel.candidate_id.is_(None),
                    CandidateMeaningModel.meaning.is_(None),
                )
            )
        )
        if source_id is not None:
            stmt = stmt.where(StoredCandidateModel.source_id == source_id)
        if only_active:
            stmt = stmt.where(
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]
                )
            )
        if sort_order == CandidateSortOrder.CHRONOLOGICAL:
            stmt = stmt.order_by(StoredCandidateModel.id.asc())
        else:
            # RELEVANCE (default)
            stmt = stmt.order_by(
                StoredCandidateModel.is_sweet_spot.desc(),
                StoredCandidateModel.zipf_frequency.desc(),
                StoredCandidateModel.cefr_level.desc(),
            )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows]

    def count_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
    ) -> int:
        stmt = (
            select(func.count(StoredCandidateModel.id))
            .outerjoin(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                or_(
                    CandidateMeaningModel.candidate_id.is_(None),
                    CandidateMeaningModel.meaning.is_(None),
                )
            )
        )
        if source_id is not None:
            stmt = stmt.where(StoredCandidateModel.source_id == source_id)
        if only_active:
            stmt = stmt.where(
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]
                )
            )
        return self._session.execute(stmt).scalar() or 0

    def mark_queued_bulk(self, candidate_ids: list[int]) -> None:
        if not candidate_ids:
            return
        existing_ids = set(
            self._session.execute(
                select(CandidateMeaningModel.candidate_id).where(
                    CandidateMeaningModel.candidate_id.in_(candidate_ids)
                )
            ).scalars().all()
        )
        for cid in candidate_ids:
            if cid in existing_ids:
                self._session.execute(
                    update(CandidateMeaningModel)
                    .where(CandidateMeaningModel.candidate_id == cid)
                    .values(status=EnrichmentStatus.QUEUED.value, error=None)
                )
            else:
                self._session.add(CandidateMeaningModel(
                    candidate_id=cid,
                    meaning=None,
                    ipa=None,
                    status=EnrichmentStatus.QUEUED.value,
                    error=None,
                    generated_at=None,
                ))
        self._session.flush()

    def mark_running(self, candidate_id: int) -> None:
        self._session.execute(
            update(CandidateMeaningModel)
            .where(CandidateMeaningModel.candidate_id == candidate_id)
            .values(status=EnrichmentStatus.RUNNING.value)
        )
        self._session.flush()

    def mark_failed(self, candidate_id: int, error: str) -> None:
        self._session.execute(
            update(CandidateMeaningModel)
            .where(CandidateMeaningModel.candidate_id == candidate_id)
            .values(status=EnrichmentStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def mark_batch_failed(self, candidate_ids: list[int], error: str) -> None:
        if not candidate_ids:
            return
        self._session.execute(
            update(CandidateMeaningModel)
            .where(CandidateMeaningModel.candidate_id.in_(candidate_ids))
            .values(status=EnrichmentStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def get_candidate_ids_by_status(
        self, source_id: int, status: EnrichmentStatus,
    ) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(
                CandidateMeaningModel,
                CandidateMeaningModel.candidate_id == StoredCandidateModel.id,
            )
            .where(
                StoredCandidateModel.source_id == source_id,
                CandidateMeaningModel.status == status.value,
            )
        )
        return [row[0] for row in self._session.execute(stmt).all()]
