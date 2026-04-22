from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_pronunciation_repository import (
    CandidatePronunciationRepository,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import (
    CandidatePronunciationModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation


class SqlaCandidatePronunciationRepository(CandidatePronunciationRepository):
    """SQLAlchemy implementation of CandidatePronunciationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidatePronunciation | None:
        model = self._session.get(CandidatePronunciationModel, candidate_id)
        return model.to_entity() if model else None

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidatePronunciation]:
        if not candidate_ids:
            return {}
        stmt = select(CandidatePronunciationModel).where(
            CandidatePronunciationModel.candidate_id.in_(candidate_ids)
        )
        rows = self._session.execute(stmt).scalars().all()
        return {row.candidate_id: row.to_entity() for row in rows}

    def upsert(self, pronunciation: CandidatePronunciation) -> None:
        existing = self._session.get(CandidatePronunciationModel, pronunciation.candidate_id)
        if existing is None:
            self._session.add(CandidatePronunciationModel.from_entity(pronunciation))
        else:
            existing.us_audio_path = pronunciation.us_audio_path
            existing.uk_audio_path = pronunciation.uk_audio_path
            existing.generated_at = pronunciation.generated_at
        self._session.flush()

    def get_eligible_candidate_ids(self, source_id: int) -> list[int]:
        has_pron = select(CandidatePronunciationModel.candidate_id).subquery()
        stmt = (
            select(StoredCandidateModel.id)
            .outerjoin(has_pron, StoredCandidateModel.id == has_pron.c.candidate_id)
            .where(
                StoredCandidateModel.source_id == source_id,
                StoredCandidateModel.status.in_(
                    [CandidateStatus.PENDING.value, CandidateStatus.LEARN.value]
                ),
                has_pron.c.candidate_id.is_(None),
            )
        )
        rows = self._session.execute(stmt).all()
        return [row[0] for row in rows]
