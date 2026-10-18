from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import insert

from backend.domain.ports.anki_note_repository import AnkiNoteRepository
from backend.infrastructure.persistence.models import AnkiNoteModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaAnkiNoteRepository(AnkiNoteRepository):
    """SQLAlchemy implementation of AnkiNoteRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, note_id: int, lemma: str, pos: str | None) -> None:
        self._session.execute(
            insert(AnkiNoteModel)
            .prefix_with("OR IGNORE")
            .values(note_id=note_id, lemma=lemma, pos=pos)
        )
        self._session.flush()
