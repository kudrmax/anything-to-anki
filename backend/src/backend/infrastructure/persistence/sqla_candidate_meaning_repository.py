from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    CandidatePronunciationModel,
)
from backend.infrastructure.persistence.phrase_owners import word_ids_of
from backend.infrastructure.persistence.sqla_occurrence_repository import PhraseResultsReader

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_meaning import CandidateMeaning


class SqlaCandidateMeaningRepository(CandidateMeaningRepository):
    """SQLAlchemy implementation of CandidateMeaningRepository.

    Meanings belong to phrases; the IPA belongs to the word (its pronunciation row).
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._ipa = PhraseResultsReader(session)

    def get_by_phrase_id(self, phrase_id: int) -> CandidateMeaning | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMeaning]:
        words = word_ids_of(self._session, phrase_ids)
        if not words:
            return {}
        ipa = self._ipa.ipa_by_word(list(set(words.values())))
        rows = self._session.scalars(
            select(CandidateMeaningModel).where(CandidateMeaningModel.phrase_id.in_(list(words)))
        )
        return {
            row.phrase_id: row.to_entity(words[row.phrase_id], ipa.get(words[row.phrase_id]))
            for row in rows
        }

    def upsert_for_phrase(self, phrase_id: int, meaning: CandidateMeaning) -> None:
        """The meaning of the phrase; its IPA, when there is one, goes to the word."""
        existing = self._session.get(CandidateMeaningModel, phrase_id)
        if existing is None:
            self._session.add(CandidateMeaningModel.from_entity(phrase_id, meaning))
        else:
            existing.meaning = meaning.meaning
            existing.translation = meaning.translation
            existing.synonyms = meaning.synonyms
            existing.examples = meaning.examples
            existing.generated_at = meaning.generated_at
        if meaning.ipa is not None:
            self._set_ipa(meaning.candidate_id, meaning.ipa)
        self._session.flush()

    def delete_by_phrase_id(self, phrase_id: int) -> None:
        model = self._session.get(CandidateMeaningModel, phrase_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def _set_ipa(self, word_id: int, ipa: str) -> None:
        pronunciation = self._session.get(CandidatePronunciationModel, word_id)
        if pronunciation is None:
            self._session.add(CandidatePronunciationModel(candidate_id=word_id, ipa=ipa))
        else:
            pronunciation.ipa = ipa
