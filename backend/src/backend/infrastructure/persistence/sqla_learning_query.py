from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select

from backend.domain.ports.learning_query import LearningQuery
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import (
    AnkiNoteModel,
    AnkiSyncedCardModel,
    PhraseModel,
    StoredCandidateModel,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaLearningQuery(LearningQuery):
    """Learn words of every source whose decision phrase has no row in `anki_synced_cards`,
    and notes in `anki_notes` neither mature nor deleted."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def awaiting_export(self) -> frozenset[str]:
        exported = exists().where(AnkiSyncedCardModel.phrase_id == PhraseModel.id)
        return frozenset(self._session.scalars(
            select(func.lower(StoredCandidateModel.lemma))
            .join(
                PhraseModel,
                (PhraseModel.candidate_id == StoredCandidateModel.id)
                & PhraseModel.is_decision.is_(True),
            )
            .where(StoredCandidateModel.status == WordStatus.LEARN.value, ~exported)
            .distinct()
        ))

    def in_anki(self) -> frozenset[str]:
        return frozenset(self._session.scalars(
            select(func.lower(AnkiNoteModel.lemma))
            .where(AnkiNoteModel.matured_at.is_(None), AnkiNoteModel.deleted_at.is_(None))
            .distinct()
        ))
