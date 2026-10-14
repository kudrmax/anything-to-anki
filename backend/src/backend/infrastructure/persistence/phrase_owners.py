"""Which word a phrase belongs to."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.infrastructure.persistence.models import PhraseModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def word_ids_of(session: Session, phrase_ids: list[int]) -> dict[int, int]:
    """Phrase id → the id of its word; unknown phrases are left out."""
    if not phrase_ids:
        return {}
    rows = session.execute(
        select(PhraseModel.id, PhraseModel.candidate_id).where(PhraseModel.id.in_(phrase_ids))
    ).all()
    return {phrase_id: word_id for phrase_id, word_id in rows}
