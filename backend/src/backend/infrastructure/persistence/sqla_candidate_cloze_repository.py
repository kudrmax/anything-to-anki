from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
from backend.infrastructure.persistence.models import CandidateClozeModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_cloze import CandidateCloze


class SqlaCandidateClozeRepository(CandidateClozeRepository):
    """SQLAlchemy implementation of CandidateClozeRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_candidate_id(self, candidate_id: int) -> CandidateCloze | None:
        model = self._session.get(CandidateClozeModel, candidate_id)
        return model.to_entity() if model else None

    def upsert(self, cloze: CandidateCloze) -> None:
        existing = self._session.get(CandidateClozeModel, cloze.candidate_id)
        if existing is None:
            self._session.add(CandidateClozeModel.from_entity(cloze))
        else:
            existing.hidden_word_indices = json.dumps(list(cloze.hidden_word_indices))
            existing.hint_kind = cloze.hint_kind.value
            existing.custom_hint = cloze.custom_hint
            existing.phrase = cloze.phrase
        self._session.flush()

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        model = self._session.get(CandidateClozeModel, candidate_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
