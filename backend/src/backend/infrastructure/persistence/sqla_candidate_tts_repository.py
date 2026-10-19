from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
from backend.infrastructure.persistence.models import CandidateTTSModel
from backend.infrastructure.persistence.phrase_owners import word_ids_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_tts import CandidateTTS


class SqlaCandidateTTSRepository(CandidateTTSRepository):
    """SQLAlchemy implementation of CandidateTTSRepository: the speech of phrases."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_phrase_id(self, phrase_id: int) -> CandidateTTS | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateTTS]:
        words = word_ids_of(self._session, phrase_ids)
        if not words:
            return {}
        rows = self._session.scalars(
            select(CandidateTTSModel).where(CandidateTTSModel.phrase_id.in_(list(words)))
        )
        return {row.phrase_id: row.to_entity(words[row.phrase_id]) for row in rows}

    def upsert_for_phrase(self, phrase_id: int, tts: CandidateTTS) -> None:
        existing = self._session.get(CandidateTTSModel, phrase_id)
        if existing is None:
            self._session.add(CandidateTTSModel.from_entity(phrase_id, tts))
        else:
            existing.audio_path = tts.audio_path
            existing.generated_at = tts.generated_at
        self._session.flush()

    def delete_by_phrase_id(self, phrase_id: int) -> None:
        model = self._session.get(CandidateTTSModel, phrase_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
