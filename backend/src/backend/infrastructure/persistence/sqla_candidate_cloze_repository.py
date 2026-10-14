from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import update

from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.infrastructure.persistence.models import CandidateClozeModel, PhraseModel
from backend.infrastructure.persistence.primary_phrase import PrimaryPhrases

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.candidate_cloze import CandidateCloze


class SqlaCandidateClozeRepository(CandidateClozeRepository):
    """SQLAlchemy implementation of CandidateClozeRepository: the cloze markup of phrases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._primary = PrimaryPhrases(session)

    # ── by phrase ──────────────────────────────────────────────────────

    def get_by_phrase_id(self, phrase_id: int) -> CandidateCloze | None:
        model = self._session.get(CandidateClozeModel, phrase_id)
        if model is None:
            return None
        word_id = self._primary.word_ids([phrase_id])[phrase_id]
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
        self._decision_kind(phrase_id, DecisionKind.CLOZE)
        self._session.flush()

    def delete_by_phrase_id(self, phrase_id: int) -> None:
        model = self._session.get(CandidateClozeModel, phrase_id)
        if model is not None:
            self._session.delete(model)
            self._decision_kind(phrase_id, DecisionKind.LEARN)
            self._session.flush()

    # TRANSITIONAL(words-phrases): removed in Task 10
    def _decision_kind(self, phrase_id: int, kind: DecisionKind) -> None:
        """A decision phrase with cloze markup goes to Anki as a cloze card."""
        self._session.execute(
            update(PhraseModel)
            .where(PhraseModel.id == phrase_id, PhraseModel.is_decision.is_(True))
            .values(decision_kind=kind.value)
        )

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    def get_by_candidate_id(self, candidate_id: int) -> CandidateCloze | None:
        phrase_id = self._primary.id(candidate_id)
        return self.get_by_phrase_id(phrase_id) if phrase_id is not None else None

    def upsert(self, cloze: CandidateCloze) -> None:
        phrase_id = self._primary.id(cloze.candidate_id)
        if phrase_id is not None:
            self.upsert_for_phrase(phrase_id, cloze)

    def delete_by_candidate_id(self, candidate_id: int) -> None:
        phrase_id = self._primary.id(candidate_id)
        if phrase_id is not None:
            self.delete_by_phrase_id(phrase_id)
