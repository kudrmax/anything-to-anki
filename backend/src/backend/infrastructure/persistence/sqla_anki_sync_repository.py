from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.infrastructure.persistence.models import AnkiSyncedCardModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaAnkiSyncRepository(AnkiSyncRepository):
    """SQLAlchemy implementation of AnkiSyncRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_synced_candidate_ids(self, candidate_ids: list[int]) -> set[int]:
        if not candidate_ids:
            return set()
        rows = (
            self._session.query(AnkiSyncedCardModel.candidate_id)
            .filter(AnkiSyncedCardModel.candidate_id.in_(candidate_ids))
            .all()
        )
        return {row.candidate_id for row in rows}

    def mark_synced(self, candidate_id: int, anki_note_id: int) -> None:
        record = AnkiSyncedCardModel(candidate_id=candidate_id, anki_note_id=anki_note_id)
        self._session.add(record)
        self._session.flush()
