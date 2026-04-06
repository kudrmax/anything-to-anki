from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.entities.generation_job import GenerationJob
from backend.domain.entities.known_word import KnownWord
from backend.domain.entities.prompt_template import PromptTemplate
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.generation_job_status import GenerationJobStatus
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.source_type import SourceType
from backend.infrastructure.persistence.database import Base


class SourceModel(Base):
    """SQLAlchemy model for text sources."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> Source:
        return Source(
            id=self.id,
            raw_text=self.raw_text,
            title=self.title,
            cleaned_text=self.cleaned_text,
            status=SourceStatus(self.status),
            source_type=SourceType(self.source_type),
            error_message=self.error_message,
            processing_stage=ProcessingStage(self.processing_stage) if self.processing_stage else None,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(source: Source) -> SourceModel:
        return SourceModel(
            raw_text=source.raw_text,
            title=source.title,
            status=source.status.value,
            source_type=source.source_type.value,
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
    surface_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_phrasal_verb: Mapped[bool] = mapped_column(nullable=False, default=False)

    def to_entity(self) -> StoredCandidate:
        return StoredCandidate(
            id=self.id,
            source_id=self.source_id,
            lemma=self.lemma,
            pos=self.pos,
            cefr_level=self.cefr_level or None,
            zipf_frequency=self.zipf_frequency,
            is_sweet_spot=self.is_sweet_spot,
            context_fragment=self.context_fragment,
            fragment_purity=self.fragment_purity,
            occurrences=self.occurrences,
            surface_form=self.surface_form,
            meaning=self.meaning,
            ipa=self.ipa,
            is_phrasal_verb=self.is_phrasal_verb,
            status=CandidateStatus(self.status),
        )

    @staticmethod
    def from_entity(candidate: StoredCandidate) -> StoredCandidateModel:
        return StoredCandidateModel(
            source_id=candidate.source_id,
            lemma=candidate.lemma,
            pos=candidate.pos,
            cefr_level=candidate.cefr_level or "",
            zipf_frequency=candidate.zipf_frequency,
            is_sweet_spot=candidate.is_sweet_spot,
            context_fragment=candidate.context_fragment,
            fragment_purity=candidate.fragment_purity,
            occurrences=candidate.occurrences,
            surface_form=candidate.surface_form,
            meaning=candidate.meaning,
            ipa=candidate.ipa,
            is_phrasal_verb=candidate.is_phrasal_verb,
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


class PromptTemplateModel(Base):
    """SQLAlchemy model for AI prompt templates keyed by function."""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    function_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)

    def to_entity(self) -> PromptTemplate:
        return PromptTemplate(
            id=self.id,
            function_key=self.function_key,
            system_prompt=self.system_prompt,
            user_template=self.user_template,
        )


class GenerationJobModel(Base):
    """SQLAlchemy model for background generation jobs.

    One job = one batch of candidates (up to 15 words).
    """

    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> GenerationJob:
        import json
        return GenerationJob(
            id=self.id,
            source_id=self.source_id,
            status=GenerationJobStatus(self.status),
            total_candidates=self.total_candidates,
            candidate_ids=json.loads(self.candidate_ids_json),
            processed_candidates=self.processed_candidates,
            failed_candidates=self.failed_candidates,
            skipped_candidates=self.skipped_candidates,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(job: GenerationJob) -> GenerationJobModel:
        import json
        return GenerationJobModel(
            source_id=job.source_id,
            status=job.status.value,
            total_candidates=job.total_candidates,
            candidate_ids_json=json.dumps(job.candidate_ids),
            processed_candidates=job.processed_candidates,
            failed_candidates=job.failed_candidates,
            skipped_candidates=job.skipped_candidates,
            created_at=job.created_at,
        )
