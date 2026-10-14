from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import insert, select, update

from backend.domain.ports.anki_note_repository import AnkiNoteRepository
from backend.infrastructure.persistence.models import AnkiNoteModel

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

    from backend.domain.entities.anki_note import AnkiNote


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

    def pending(self) -> list[AnkiNote]:
        rows = self._session.scalars(
            select(AnkiNoteModel)
            .where(AnkiNoteModel.matured_at.is_(None), AnkiNoteModel.deleted_at.is_(None))
            .order_by(AnkiNoteModel.note_id)
        )
        return [row.to_entity() for row in rows]

    def mark_matured(self, note_ids: list[int], at: datetime) -> None:
        self._mark(note_ids, matured_at=at)

    def mark_deleted(self, note_ids: list[int], at: datetime) -> None:
        self._mark(note_ids, deleted_at=at)

    def _mark(self, note_ids: list[int], **values: datetime) -> None:
        if not note_ids:
            return
        self._session.execute(
            update(AnkiNoteModel).where(AnkiNoteModel.note_id.in_(note_ids)).values(**values)
        )
        self._session.flush()
