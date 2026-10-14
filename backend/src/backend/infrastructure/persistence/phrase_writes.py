"""Writes every change of a phrase's text or results goes through."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import delete, insert

from backend.infrastructure.persistence.models import (
    CandidateClozeModel,
    CandidateMeaningModel,
    CandidateMediaModel,
    CandidateTTSModel,
    PhraseWordModel,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from sqlalchemy.orm import Session

RESULT_MODELS = (
    CandidateMeaningModel, CandidateMediaModel, CandidateTTSModel, CandidateClozeModel,
)
# Ids per `IN (…)`: well under SQLite's limit of bound parameters.
SQL_IN_CHUNK = 500
_WORD_LEMMA = 2


def chunks(ids: Sequence[int]) -> Iterator[list[int]]:
    for start in range(0, len(ids), SQL_IN_CHUNK):
        yield list(ids[start:start + SQL_IN_CHUNK])


class PhraseWords:
    """Keeps `phrase_words` equal to the words of the text a phrase shows, lowercase."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def rewrite(self, shown_texts: dict[int, str]) -> None:
        """`shown_texts`: phrase id → the stored phrase it shows."""
        for chunk in chunks(list(shown_texts)):
            self._session.execute(
                delete(PhraseWordModel).where(PhraseWordModel.phrase_id.in_(chunk))
            )
        rows = [
            {"phrase_id": phrase_id, "lemma": lemma}
            for phrase_id, stored in shown_texts.items()
            for lemma in sorted(
                {word[_WORD_LEMMA].lower() for word in json.loads(stored)["words"]},
            )
        ]
        if rows:
            self._session.execute(insert(PhraseWordModel), rows)


def drop_results(session: Session, phrase_ids: Sequence[int]) -> None:
    """Everything made for the phrases except polish, which lives on the phrase itself."""
    for chunk in chunks(phrase_ids):
        for model in RESULT_MODELS:
            session.execute(delete(model).where(model.phrase_id.in_(chunk)))
