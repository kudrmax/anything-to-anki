from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.domain.entities.dictionary_entry import DictionaryEntry
from backend.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    pass


class DictionaryCacheModel(Base):
    """SQLAlchemy model for cached dictionary API responses."""

    __tablename__ = "dictionary_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pos: Mapped[str] = mapped_column(String(10), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    __table_args__ = (UniqueConstraint("lemma", "pos", name="uq_dict_cache_lemma_pos"),)

    def to_entry(self) -> DictionaryEntry:
        return DictionaryEntry(
            lemma=self.lemma,
            pos=self.pos,
            definition=self.definition,
            ipa=self.ipa,
        )


class DictionaryCacheRepository:
    """In-infrastructure-only repository for dictionary cache (no domain port needed)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, lemma: str, pos: str) -> DictionaryEntry | None:
        model = (
            self._session.query(DictionaryCacheModel)
            .filter_by(lemma=lemma, pos=pos)
            .first()
        )
        return model.to_entry() if model else None

    def save(self, entry: DictionaryEntry) -> None:
        existing = (
            self._session.query(DictionaryCacheModel)
            .filter_by(lemma=entry.lemma, pos=entry.pos)
            .first()
        )
        if existing:
            existing.definition = entry.definition
            existing.ipa = entry.ipa
            existing.fetched_at = datetime.now(tz=UTC)
        else:
            self._session.add(
                DictionaryCacheModel(
                    lemma=entry.lemma,
                    pos=entry.pos,
                    definition=entry.definition,
                    ipa=entry.ipa,
                )
            )
        self._session.flush()
