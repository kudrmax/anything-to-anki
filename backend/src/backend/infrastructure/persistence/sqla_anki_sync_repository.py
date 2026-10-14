from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.infrastructure.persistence.models import AnkiSyncedCardModel
from backend.infrastructure.persistence.primary_phrase import PrimaryPhrases

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaAnkiSyncRepository(AnkiSyncRepository):
    """SQLAlchemy implementation of AnkiSyncRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._primary = PrimaryPhrases(session)

    def get_synced_candidate_ids(self, candidate_ids: list[int]) -> set[int]:
        if not candidate_ids:
            return set()
        rows = (
            self._session.query(AnkiSyncedCardModel.candidate_id)
            .filter(AnkiSyncedCardModel.candidate_id.in_(candidate_ids))
            .all()
        )
        return {row.candidate_id for row in rows}

    def mark_synced(
        self, candidate_id: int, anki_note_id: int, phrase_id: int | None = None,
    ) -> None:
        if phrase_id is None:
            # TRANSITIONAL(words-phrases): removed in Task 10
            phrase_id = self._primary.id(candidate_id)
        record = AnkiSyncedCardModel(
            candidate_id=candidate_id, phrase_id=phrase_id, anki_note_id=anki_note_id,
        )
        self._session.add(record)
        self._session.flush()
