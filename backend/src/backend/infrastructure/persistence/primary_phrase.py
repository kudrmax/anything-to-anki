# TRANSITIONAL(words-phrases): removed in Task 10
"""The phrase through which the card-shaped API still sees a word.

Until the read side works with phrases, a word looks like one card: the phrase of its
decision, else its first shown phrase that is not skipped, else its first phrase.
A word whose primary phrase is skipped reads as SKIP.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, case, exists, select
from sqlalchemy.orm import aliased

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import PhraseModel, StoredCandidateModel

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement, ScalarSelect
    from sqlalchemy.orm import Session

ACTIVE_STATUSES = (CandidateStatus.PENDING.value, CandidateStatus.LEARN.value)


def primary_phrase_id(word_id: ColumnElement[int]) -> ScalarSelect[int]:
    """The id of the primary phrase of the word, as a correlated subquery."""
    phrase = aliased(PhraseModel)
    shown_and_open = case(
        (and_(phrase.shown_by.is_not(None), phrase.skipped.is_(False)), 1), else_=0,
    )
    return (
        select(phrase.id)
        .where(phrase.candidate_id == word_id)
        .order_by(phrase.is_decision.desc(), shown_and_open.desc(), phrase.id.asc())
        .limit(1)
        .scalar_subquery()
    )


def word_is_active() -> ColumnElement[bool]:
    """A word still to work on: pending or learn, its primary phrase not skipped."""
    primary = aliased(PhraseModel)
    return and_(
        StoredCandidateModel.status.in_(ACTIVE_STATUSES),
        exists().where(
            primary.id == primary_phrase_id(StoredCandidateModel.id),
            primary.skipped.is_(False),
        ),
    )


class PrimaryPhrases:
    """Reads the primary phrases of words."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ids(self, word_ids: list[int]) -> dict[int, int]:
        """Word id → its primary phrase id; a word without phrases is left out."""
        if not word_ids:
            return {}
        rows = self._session.execute(
            select(StoredCandidateModel.id, primary_phrase_id(StoredCandidateModel.id))
            .where(StoredCandidateModel.id.in_(word_ids))
        ).all()
        return {word_id: phrase_id for word_id, phrase_id in rows if phrase_id is not None}

    def id(self, word_id: int) -> int | None:
        return self.ids([word_id]).get(word_id)

    def models(self, word_ids: list[int]) -> dict[int, PhraseModel]:
        """Word id → its primary phrase."""
        ids = self.ids(word_ids)
        if not ids:
            return {}
        by_id = {
            model.id: model
            for model in self._session.scalars(
                select(PhraseModel).where(PhraseModel.id.in_(list(ids.values())))
            )
        }
        return {word_id: by_id[phrase_id] for word_id, phrase_id in ids.items()}

    def word_ids(self, phrase_ids: list[int]) -> dict[int, int]:
        """Phrase id → the id of its word."""
        if not phrase_ids:
            return {}
        rows = self._session.execute(
            select(PhraseModel.id, PhraseModel.candidate_id).where(PhraseModel.id.in_(phrase_ids))
        ).all()
        return {phrase_id: word_id for phrase_id, word_id in rows}


def status_of(word: StoredCandidateModel, primary: PhraseModel) -> CandidateStatus:
    if primary.skipped:
        return CandidateStatus.SKIP
    return CandidateStatus(word.status)


def words_of_source(session: Session, source_id: int) -> list[int]:
    return list(session.scalars(
        select(StoredCandidateModel.id).where(StoredCandidateModel.source_id == source_id)
    ))
