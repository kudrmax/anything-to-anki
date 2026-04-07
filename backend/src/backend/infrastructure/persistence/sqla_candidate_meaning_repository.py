from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
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
