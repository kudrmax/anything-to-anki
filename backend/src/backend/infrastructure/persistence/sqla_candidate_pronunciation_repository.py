from __future__ import annotations

from typing import TYPE_CHECKING

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

    def upsert(self, pronunciation: CandidatePronunciation) -> None:
        existing = self._session.get(CandidatePronunciationModel, pronunciation.candidate_id)
        if existing is None:
            self._session.add(CandidatePronunciationModel.from_entity(pronunciation))
        else:
            existing.us_audio_path = pronunciation.us_audio_path
            existing.uk_audio_path = pronunciation.uk_audio_path
            existing.generated_at = pronunciation.generated_at
        self._session.flush()
