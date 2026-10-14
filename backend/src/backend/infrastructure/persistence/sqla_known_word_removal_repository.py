from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, exists, insert, select

from backend.domain.ports.known_word_removal_repository import KnownWordRemovalRepository
from backend.infrastructure.persistence.models import KnownWordRemovalModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaKnownWordRemovalRepository(KnownWordRemovalRepository):
    """SQLAlchemy implementation of KnownWordRemovalRepository; lemmas are kept lowercase."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lemma: str) -> None:
        self._session.execute(
            insert(KnownWordRemovalModel)
            .prefix_with("OR REPLACE")
            .values(lemma=lemma.lower(), removed_at=datetime.now(tz=UTC))
        )
        self._session.flush()

    def discard(self, lemma: str) -> None:
        self._session.execute(
            delete(KnownWordRemovalModel).where(KnownWordRemovalModel.lemma == lemma.lower())
        )
        self._session.flush()

    def contains(self, lemma: str) -> bool:
        return bool(self._session.scalar(
            select(exists().where(KnownWordRemovalModel.lemma == lemma.lower()))
        ))
