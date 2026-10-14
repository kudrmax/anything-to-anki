from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import exists, func, select

from backend.domain.ports.learning_query import LearningQuery
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import AnkiSyncedCardModel, StoredCandidateModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaLearningQuery(LearningQuery):
    """Learn words of every source without a row in `anki_synced_cards`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def learning_lemmas(self) -> frozenset[str]:
        exported = exists().where(AnkiSyncedCardModel.candidate_id == StoredCandidateModel.id)
        return frozenset(self._session.scalars(
            select(func.lower(StoredCandidateModel.lemma))
            .where(StoredCandidateModel.status == WordStatus.LEARN.value, ~exported)
            .distinct()
        ))
