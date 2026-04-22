from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
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
            existing.translation = meaning.translation
            existing.synonyms = meaning.synonyms
            existing.examples = meaning.examples
            existing.ipa = meaning.ipa
            existing.generated_at = meaning.generated_at
        self._session.flush()

    def get_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
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
