from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.infrastructure.persistence.models import AnkiSyncedCardModel
from backend.infrastructure.persistence.phrase_writes import chunks

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaAnkiSyncRepository(AnkiSyncRepository):
    """SQLAlchemy implementation of AnkiSyncRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_synced_phrase_ids(self, phrase_ids: list[int]) -> set[int]:
        synced: set[int] = set()
        for chunk in chunks(phrase_ids):
            synced.update(
                phrase_id
                for phrase_id in self._session.scalars(
                    select(AnkiSyncedCardModel.phrase_id)
                    .where(AnkiSyncedCardModel.phrase_id.in_(chunk))
                )
                if phrase_id is not None
            )
        return synced

    def mark_synced(self, candidate_id: int, anki_note_id: int, phrase_id: int) -> None:
        record = AnkiSyncedCardModel(
            candidate_id=candidate_id, phrase_id=phrase_id, anki_note_id=anki_note_id,
        )
        self._session.add(record)
        self._session.flush()
