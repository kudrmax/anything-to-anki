from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_pronunciation_repository import (
    CandidatePronunciationRepository,
)
from backend.infrastructure.persistence.models import (
    CandidatePronunciationModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation


class SqlaCandidatePronunciationRepository(CandidatePronunciationRepository):
    """SQLAlchemy implementation of CandidatePronunciationRepository.

    The row of a word also keeps its IPA; a row with only the IPA is not a pronunciation.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidatePronunciation | None:
        return self.get_by_candidate_ids([candidate_id]).get(candidate_id)

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidatePronunciation]:
        if not candidate_ids:
            return {}
        stmt = select(CandidatePronunciationModel).where(
            CandidatePronunciationModel.candidate_id.in_(candidate_ids),
            CandidatePronunciationModel.is_generated(),
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
