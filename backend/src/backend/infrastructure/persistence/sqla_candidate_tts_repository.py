from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import (
    CandidateTTSModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_tts import CandidateTTS


class SqlaCandidateTTSRepository(CandidateTTSRepository):
    """SQLAlchemy implementation of CandidateTTSRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateTTS | None:
        model = self._session.get(CandidateTTSModel, candidate_id)
        return model.to_entity() if model else None

    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidateTTS]:
        if not candidate_ids:
            return {}
        stmt = select(CandidateTTSModel).where(
            CandidateTTSModel.candidate_id.in_(candidate_ids),
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def upsert(self, tts: CandidateTTS) -> None:
        existing = self._session.get(CandidateTTSModel, tts.candidate_id)
        if existing is None:
            self._session.add(CandidateTTSModel.from_entity(tts))
        else:
            existing.audio_path = tts.audio_path
            existing.generated_at = tts.generated_at
        self._session.flush()

    def get_eligible_candidate_ids(self, source_id: int) -> list[int]:
        has_tts = select(CandidateTTSModel.candidate_id).subquery()
        stmt = (
            select(StoredCandidateModel.id)
            .outerjoin(has_tts, StoredCandidateModel.id == has_tts.c.candidate_id)
            .where(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value],
                ),
                has_tts.c.candidate_id.is_(None),
            )
        )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows]
