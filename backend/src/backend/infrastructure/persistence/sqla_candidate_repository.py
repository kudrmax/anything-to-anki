# backend/src/backend/infrastructure/persistence/sqla_candidate_repository.py
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    CandidateMeaningImageModel,
    CandidatePronunciationModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime

    from sqlalchemy import ColumnElement
    from sqlalchemy.orm import Session

    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.built_analysis import WordKey


class SqlaCandidateRepository(CandidateRepository):
    """SQLAlchemy implementation of CandidateRepository: the words of sources, with their
    pronunciation and picture attached."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_word(self, word: StoredCandidate) -> int:
        model = StoredCandidateModel.from_entity(word)
        model.status = WordStatus.NEW.value
        self._session.add(model)
        self._session.flush()
        return model.id

    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        return self._read(StoredCandidateModel.source_id == source_id)

    def word_id(self, source_id: int, key: WordKey) -> int | None:
        return self._session.scalar(
            select(StoredCandidateModel.id).where(
                StoredCandidateModel.source_id == source_id,
                func.lower(StoredCandidateModel.lemma) == key.lemma,
                StoredCandidateModel.is_phrasal_verb.is_(key.is_phrasal_verb),
            )
        )

    def get_by_id(self, candidate_id: int) -> StoredCandidate | None:
        found = self._read(StoredCandidateModel.id == candidate_id)
        return found[0] if found else None

    def count_learning_in_anki(self) -> int:
        return self._session.scalar(
            select(func.count(StoredCandidateModel.id))
            .where(StoredCandidateModel.learning_in_anki())
        ) or 0

    def count_all(self) -> int:
        result = self._session.query(func.count(StoredCandidateModel.id)).scalar()
        return result or 0

    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        if not candidate_ids:
            return []
        found = self._read(StoredCandidateModel.id.in_(candidate_ids))
        order_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
        found.sort(key=lambda c: order_map.get(c.id or 0, len(order_map)))
        return found

    def get_by_lemma(self, lemma: str) -> list[StoredCandidate]:
        return self._read(func.lower(StoredCandidateModel.lemma) == lemma.lower())

    def chosen_to_learn(self, source_ids: Collection[int] | None = None) -> list[StoredCandidate]:
        if source_ids is None:
            return self._read(StoredCandidateModel.chosen_to_learn())
        return [
            word for chunk in chunks(list(source_ids))
            for word in self._read(
                StoredCandidateModel.chosen_to_learn(),
                StoredCandidateModel.source_id.in_(chunk),
            )
        ]

    def get_lemma_map(self, candidate_ids: list[int]) -> dict[int, str]:
        if not candidate_ids:
            return {}
        rows = (
            self._session.query(StoredCandidateModel.id, StoredCandidateModel.lemma)
            .filter(StoredCandidateModel.id.in_(candidate_ids))
            .all()
        )
        return {row.id: row.lemma for row in rows}

    def delete_by_source(self, source_id: int) -> None:
        """Delete all words of a source.

        Their phrases, results and jobs go by DB-level ON DELETE CASCADE; their Anki
        bindings stay, with no card (SET NULL). Requires PRAGMA foreign_keys = ON (set in
        database.py).
        """
        models = (
            self._session.query(StoredCandidateModel)
            .filter(StoredCandidateModel.source_id == source_id)
            .all()
        )
        for model in models:
            self._session.delete(model)
        self._session.flush()

    def set_studied_at(self, word_id: int, studied_at: datetime | None) -> None:
        model = self._session.get(StoredCandidateModel, word_id)
        if model is not None:
            model.studied_at = studied_at
            self._session.flush()

    def last_studied(self, source_ids: Collection[int]) -> dict[int, datetime]:
        found: dict[int, datetime] = {}
        for chunk in chunks(list(source_ids)):
            stmt = (
                select(StoredCandidateModel.source_id, func.max(StoredCandidateModel.studied_at))
                .where(
                    StoredCandidateModel.source_id.in_(chunk),
                    StoredCandidateModel.studied_at.is_not(None),
                )
                .group_by(StoredCandidateModel.source_id)
            )
            found.update({
                source_id: studied for source_id, studied in self._session.execute(stmt)
                if studied is not None
            })
        return found

    # ── private helpers ────────────────────────────────────────────────

    def _read(self, *where: ColumnElement[bool]) -> list[StoredCandidate]:
        stmt = select(StoredCandidateModel).where(*where).order_by(StoredCandidateModel.id)
        return self._with_results(list(self._session.scalars(stmt).unique()))

    def _with_results(self, words: list[StoredCandidateModel]) -> list[StoredCandidate]:
        """Words with their pronunciation and picture attached."""
        ids = [w.id for w in words]
        prons = {
            r.candidate_id: r.to_entity()
            for r in self._session.scalars(
                select(CandidatePronunciationModel)
                .where(
                    CandidatePronunciationModel.candidate_id.in_(ids),
                    CandidatePronunciationModel.is_generated(),
                )
            )
        }
        images = {
            r.candidate_id: r.to_entity()
            for r in self._session.scalars(
                select(CandidateMeaningImageModel)
                .where(CandidateMeaningImageModel.candidate_id.in_(ids))
            )
        }
        read: list[StoredCandidate] = []
        for word in words:
            entity = word.to_entity()
            entity.pronunciation = prons.get(word.id)
            entity.meaning_image = images.get(word.id)
            read.append(entity)
        return read
