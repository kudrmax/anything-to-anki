from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    CandidatePronunciationModel,
    PhraseModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.primary_phrase import (
    PrimaryPhrases,
    primary_phrase_id,
    word_is_active,
    words_of_source,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import PhraseResultsReader

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement, Select
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_meaning import CandidateMeaning


class SqlaCandidateMeaningRepository(CandidateMeaningRepository):
    """SQLAlchemy implementation of CandidateMeaningRepository.

    Meanings belong to phrases; the IPA belongs to the word (its pronunciation row).
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._primary = PrimaryPhrases(session)
        self._ipa = PhraseResultsReader(session)

    # ── by phrase ──────────────────────────────────────────────────────

    def get_by_phrase_id(self, phrase_id: int) -> CandidateMeaning | None:
        return self.get_by_phrase_ids([phrase_id]).get(phrase_id)

    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMeaning]:
        words = self._primary.word_ids(phrase_ids)
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

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaning | None:
        return self.get_by_candidate_ids([candidate_id]).get(candidate_id)

    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMeaning]:
        return self.get_by_candidate_ids(words_of_source(self._session, source_id))

    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMeaning]:
        primaries = self._primary.ids(candidate_ids)
        by_phrase = self.get_by_phrase_ids(list(primaries.values()))
        return {
            word_id: by_phrase[phrase_id]
            for word_id, phrase_id in primaries.items()
            if phrase_id in by_phrase
        }

    def upsert(self, meaning: CandidateMeaning) -> None:
        phrase_id = self._primary.id(meaning.candidate_id)
        if phrase_id is not None:
            self.upsert_for_phrase(phrase_id, meaning)

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        phrase_id = self._primary.id(candidate_id)
        if phrase_id is not None:
            self.delete_by_phrase_id(phrase_id)

    def get_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
    ) -> list[int]:
        stmt = self._without_meaning(select(StoredCandidateModel.id), source_id, only_active)
        return [row[0] for row in self._session.execute(stmt).all()]

    def count_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
    ) -> int:
        stmt = self._without_meaning(
            select(func.count(StoredCandidateModel.id)), source_id, only_active,
        )
        return self._session.execute(stmt).scalar() or 0

    # ── private helpers ────────────────────────────────────────────────

    def _without_meaning[T: tuple[int]](
        self, stmt: Select[T], source_id: int | None, only_active: bool,
    ) -> Select[T]:
        conditions: list[ColumnElement[bool]] = [
            or_(CandidateMeaningModel.phrase_id.is_(None), CandidateMeaningModel.meaning.is_(None)),
        ]
        if source_id is not None:
            conditions.append(StoredCandidateModel.source_id == source_id)
        if only_active:
            conditions.append(word_is_active())
        return (
            stmt.select_from(StoredCandidateModel)
            .join(PhraseModel, PhraseModel.id == primary_phrase_id(StoredCandidateModel.id))
            .outerjoin(CandidateMeaningModel, CandidateMeaningModel.phrase_id == PhraseModel.id)
            .where(*conditions)
        )

    def _set_ipa(self, word_id: int, ipa: str) -> None:
        pronunciation = self._session.get(CandidatePronunciationModel, word_id)
        if pronunciation is None:
            self._session.add(CandidatePronunciationModel(candidate_id=word_id, ipa=ipa))
        else:
            pronunciation.ipa = ipa
