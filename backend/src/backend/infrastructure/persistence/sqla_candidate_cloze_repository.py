from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
from backend.domain.value_objects.card_change import CardContentChanged
from backend.infrastructure.persistence.models import CandidateClozeModel
from backend.infrastructure.persistence.phrase_owners import word_ids_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.ports.change_recorder import ChangeRecorder


class SqlaCandidateClozeRepository(CandidateClozeRepository):
    """SQLAlchemy implementation of CandidateClozeRepository: the cloze markup of phrases.

    The markup does not decide what kind of card the phrase is: its decision does."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

    def get_by_phrase_id(self, phrase_id: int) -> CandidateCloze | None:
        model = self._session.get(CandidateClozeModel, phrase_id)
        if model is None:
            return None
        word_id = word_ids_of(self._session, [phrase_id])[phrase_id]
        return model.to_entity(word_id)

    def upsert_for_phrase(self, phrase_id: int, cloze: CandidateCloze) -> None:
        existing = self._session.get(CandidateClozeModel, phrase_id)
        if existing is None:
            self._session.add(CandidateClozeModel.from_entity(phrase_id, cloze))
        else:
            existing.hidden_word_indices = json.dumps(list(cloze.hidden_word_indices))
            existing.hint_kind = cloze.hint_kind.value
            existing.custom_hint = cloze.custom_hint
            existing.phrase = cloze.phrase
        self._session.flush()
        self._recorder.record(CardContentChanged(phrase_id))

    def delete_by_phrase_id(self, phrase_id: int) -> None:
        model = self._session.get(CandidateClozeModel, phrase_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
            self._recorder.record(CardContentChanged(phrase_id))
