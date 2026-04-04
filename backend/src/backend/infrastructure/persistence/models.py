from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.entities.known_word import KnownWord
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.database import Base


class SourceModel(Base):
    """SQLAlchemy model for text sources."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> Source:
        return Source(
            id=self.id,
            raw_text=self.raw_text,
            cleaned_text=self.cleaned_text,
            status=SourceStatus(self.status),
            error_message=self.error_message,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(source: Source) -> SourceModel:
        return SourceModel(
            raw_text=source.raw_text,
            status=source.status.value,
            created_at=source.created_at,
        )


class StoredCandidateModel(Base):
    """SQLAlchemy model for word candidates."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str] = mapped_column(String(10), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(10), nullable=False)
    zipf_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    is_sweet_spot: Mapped[bool] = mapped_column(nullable=False)
    context_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    fragment_purity: Mapped[str] = mapped_column(String(10), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")

    def to_entity(self) -> StoredCandidate:
        return StoredCandidate(
            id=self.id,
            source_id=self.source_id,
            lemma=self.lemma,
            pos=self.pos,
            cefr_level=self.cefr_level,
            zipf_frequency=self.zipf_frequency,
            is_sweet_spot=self.is_sweet_spot,
            context_fragment=self.context_fragment,
            fragment_purity=self.fragment_purity,
            occurrences=self.occurrences,
            status=CandidateStatus(self.status),
        )

    @staticmethod
    def from_entity(candidate: StoredCandidate) -> StoredCandidateModel:
        return StoredCandidateModel(
            source_id=candidate.source_id,
            lemma=candidate.lemma,
            pos=candidate.pos,
            cefr_level=candidate.cefr_level,
            zipf_frequency=candidate.zipf_frequency,
            is_sweet_spot=candidate.is_sweet_spot,
            context_fragment=candidate.context_fragment,
            fragment_purity=candidate.fragment_purity,
            occurrences=candidate.occurrences,
            status=candidate.status.value,
        )


class KnownWordModel(Base):
    """SQLAlchemy model for known-word whitelist."""

    __tablename__ = "known_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    __table_args__ = (UniqueConstraint("lemma", "pos", name="uq_known_word_lemma_pos"),)

    def to_entity(self) -> KnownWord:
        return KnownWord(
            id=self.id,
            lemma=self.lemma,
            pos=self.pos,
            created_at=self.created_at,
        )


class SettingModel(Base):
    """SQLAlchemy model for application settings (key-value)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
