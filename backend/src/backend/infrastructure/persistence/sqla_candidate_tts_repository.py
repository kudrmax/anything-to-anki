from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
from backend.infrastructure.persistence.models import (
    CandidateTTSModel,
    PhraseModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.primary_phrase import (
    PrimaryPhrases,
    primary_phrase_id,
    word_is_active,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_tts import CandidateTTS


class SqlaCandidateTTSRepository(CandidateTTSRepository):
    """SQLAlchemy implementation of CandidateTTSRepository: the speech of phrases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._primary = PrimaryPhrases(session)

    # ── by phrase ──────────────────────────────────────────────────────

    def get_by_phrase_id(self, phrase_id: int) -> CandidateTTS | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateTTS]:
        words = self._primary.word_ids(phrase_ids)
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

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    def get_by_candidate_id(self, candidate_id: int) -> CandidateTTS | None:
        return self.get_by_candidate_ids([candidate_id]).get(candidate_id)

    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidateTTS]:
        primaries = self._primary.ids(candidate_ids)
        by_phrase = self.get_by_phrase_ids(list(primaries.values()))
        return {
            word_id: by_phrase[phrase_id]
            for word_id, phrase_id in primaries.items()
            if phrase_id in by_phrase
        }

    def upsert(self, tts: CandidateTTS) -> None:
        phrase_id = self._primary.id(tts.candidate_id)
        if phrase_id is not None:
            self.upsert_for_phrase(phrase_id, tts)

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        phrase_id = self._primary.id(candidate_id)
        if phrase_id is not None:
            self.delete_by_phrase_id(phrase_id)

    def get_eligible_candidate_ids(self, source_id: int) -> list[int]:
        stmt = (
            select(StoredCandidateModel.id)
            .join(PhraseModel, PhraseModel.id == primary_phrase_id(StoredCandidateModel.id))
            .outerjoin(CandidateTTSModel, CandidateTTSModel.phrase_id == PhraseModel.id)
            .where(
                StoredCandidateModel.source_id == source_id,
                word_is_active(),
                CandidateTTSModel.phrase_id.is_(None),
            )
        )
        return [row[0] for row in self._session.execute(stmt).all()]
