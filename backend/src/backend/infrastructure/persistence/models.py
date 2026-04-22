from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.known_word import KnownWord
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from backend.domain.entities.job import Job


class SourceModel(Base):
    """SQLAlchemy model for text sources."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    input_method: Mapped[str] = mapped_column(String(20), nullable=False, default="text_pasted")
    content_type: Mapped[str] = mapped_column(String(10), nullable=False, default="text")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_track_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
            input_method=InputMethod(self.input_method),
            content_type=ContentType(self.content_type),
            source_url=self.source_url,
            error_message=self.error_message,
            processing_stage=(
                ProcessingStage(self.processing_stage) if self.processing_stage else None
            ),
            video_path=self.video_path,
            audio_track_index=self.audio_track_index,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(source: Source) -> SourceModel:
        return SourceModel(
            raw_text=source.raw_text,
            title=source.title,
            status=source.status.value,
            input_method=source.input_method.value,
            content_type=source.content_type.value,
            source_url=source.source_url,
            video_path=source.video_path,
            audio_track_index=source.audio_track_index,
            created_at=source.created_at,
        )


class CEFRBreakdownModel(Base):
    """CEFR classification breakdown: how each source voted."""

    __tablename__ = "cefr_breakdowns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    decision_method: Mapped[str] = mapped_column(String(10), nullable=False)
    cambridge: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cefrpy: Mapped[str | None] = mapped_column(String(10), nullable=True)
    efllex_distribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    oxford: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kelly: Mapped[str | None] = mapped_column(String(10), nullable=True)


def _level_to_str(level: CEFRLevel) -> str | None:
    """Convert CEFRLevel to string for DB storage. UNKNOWN -> None."""
    if level is CEFRLevel.UNKNOWN:
        return None
    return level.name


def _breakdown_to_model(breakdown: CEFRBreakdown) -> CEFRBreakdownModel:
    """Map domain CEFRBreakdown to SQLAlchemy model."""
    all_votes = [*breakdown.priority_votes, *breakdown.votes]

    cambridge: str | None = None
    cefrpy: str | None = None
    efllex_distribution: str | None = None
    oxford: str | None = None
    kelly: str | None = None

    for vote in all_votes:
        level_str = _level_to_str(vote.top_level)
        if vote.source_name == "Cambridge Dictionary":
            cambridge = level_str
        elif vote.source_name == "CEFRpy":
            cefrpy = level_str
        elif vote.source_name == "EFLLex":
            dist = {
                lvl.name: round(prob, 4)
                for lvl, prob in vote.distribution.items()
                if lvl is not CEFRLevel.UNKNOWN and prob > 0
            }
            efllex_distribution = json.dumps(dist) if dist else None
        elif vote.source_name == "Oxford 5000":
            oxford = level_str
        elif vote.source_name == "Kelly List":
            kelly = level_str

    return CEFRBreakdownModel(
        decision_method=breakdown.decision_method,
        cambridge=cambridge,
        cefrpy=cefrpy,
        efllex_distribution=efllex_distribution,
        oxford=oxford,
        kelly=kelly,
    )


def _model_to_breakdown(model: CEFRBreakdownModel) -> CEFRBreakdown:
    """Map SQLAlchemy model back to domain CEFRBreakdown.

    Final level is computed at runtime via ``resolve_cefr_level``
    instead of reading the stored ``candidates.cefr_level``.
    """
    from backend.domain.services.cefr_level_resolver import resolve_cefr_level

    def _make_vote(
        name: str,
        level_str: str | None,
        distribution_json: str | None = None,
    ) -> SourceVote:
        if distribution_json is not None:
            raw: dict[str, float] = json.loads(distribution_json)
            dist = {CEFRLevel.from_str(k): v for k, v in raw.items()}
            top = max(dist, key=lambda lvl: dist[lvl]) if dist else CEFRLevel.UNKNOWN
        elif level_str is not None:
            level = CEFRLevel.from_str(level_str)
            dist = {level: 1.0}
            top = level
        else:
            dist = {CEFRLevel.UNKNOWN: 1.0}
            top = CEFRLevel.UNKNOWN
        return SourceVote(source_name=name, distribution=dist, top_level=top)

    priority_votes = [
        _make_vote("Oxford 5000", model.oxford),
        _make_vote("Cambridge Dictionary", model.cambridge),
    ]
    votes = [
        _make_vote("CEFRpy", model.cefrpy),
        _make_vote("EFLLex", None, model.efllex_distribution),
        _make_vote("Kelly List", model.kelly),
    ]

    all_votes = [*priority_votes, *votes]
    final_level, decision_method = resolve_cefr_level(all_votes)

    return CEFRBreakdown(
        final_level=final_level,
        decision_method=decision_method,
        priority_votes=priority_votes,
        votes=votes,
    )


class StoredCandidateModel(Base):
    """SQLAlchemy model for word candidates.

    Note: meaning and media live in separate tables (CandidateMeaningModel,
    CandidateMediaModel) and are loaded by SqlaCandidateRepository, not here.
    """

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str] = mapped_column(String(10), nullable=False)
    zipf_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    is_sweet_spot: Mapped[bool] = mapped_column(nullable=False)
    context_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    fragment_purity: Mapped[str] = mapped_column(String(10), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    surface_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_phrasal_verb: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_custom_context_fragment: Mapped[bool] = mapped_column(nullable=False, default=False)
    usage_distribution_json: Mapped[str | None] = mapped_column(
        "usage_distribution", Text, nullable=True
    )

    cefr_breakdown: Mapped[CEFRBreakdownModel | None] = relationship(
        "CEFRBreakdownModel", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    def to_entity(self) -> StoredCandidate:
        """Build a StoredCandidate WITHOUT meaning/media — those are loaded
        separately by SqlaCandidateRepository which then attaches them."""
        bd: CEFRBreakdown | None = None
        if self.cefr_breakdown is not None:
            bd = _model_to_breakdown(self.cefr_breakdown)

        cefr_level: str | None = None
        if bd is not None and bd.final_level is not CEFRLevel.UNKNOWN:
            cefr_level = bd.final_level.name

        ud: UsageDistribution | None = None
        if self.usage_distribution_json is not None:
            ud = UsageDistribution(json.loads(self.usage_distribution_json))

        return StoredCandidate(
            id=self.id,
            source_id=self.source_id,
            lemma=self.lemma,
            pos=self.pos,
            cefr_level=cefr_level,
            zipf_frequency=self.zipf_frequency,
            context_fragment=self.context_fragment,
            fragment_purity=self.fragment_purity,
            occurrences=self.occurrences,
            surface_form=self.surface_form,
            is_phrasal_verb=self.is_phrasal_verb,
            has_custom_context_fragment=self.has_custom_context_fragment,
            status=CandidateStatus(self.status),
            meaning=None,
            media=None,
            cefr_breakdown=bd,
            usage_distribution=ud,
        )

    @staticmethod
    def from_entity(candidate: StoredCandidate) -> StoredCandidateModel:
        model = StoredCandidateModel(
            source_id=candidate.source_id,
            lemma=candidate.lemma,
            pos=candidate.pos,
            zipf_frequency=candidate.zipf_frequency,
            is_sweet_spot=candidate.is_sweet_spot,
            context_fragment=candidate.context_fragment,
            fragment_purity=candidate.fragment_purity,
            occurrences=candidate.occurrences,
            surface_form=candidate.surface_form,
            is_phrasal_verb=candidate.is_phrasal_verb,
            has_custom_context_fragment=candidate.has_custom_context_fragment,
            status=candidate.status.value,
        )
        if candidate.cefr_breakdown is not None:
            model.cefr_breakdown = _breakdown_to_model(candidate.cefr_breakdown)
        if candidate.usage_distribution is not None:
            dist = candidate.usage_distribution.to_dict()
            model.usage_distribution_json = json.dumps(dist) if dist else None
        return model


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


class AnkiSyncedCardModel(Base):
    """SQLAlchemy model for tracking candidates successfully synced to Anki."""

    __tablename__ = "anki_synced_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    anki_note_id: Mapped[int] = mapped_column(Integer, nullable=False)


class CandidateMeaningModel(Base):
    """SQLAlchemy model for the meaning enrichment of a candidate (1:1)."""

    __tablename__ = "candidate_meanings"

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        nullable=False,
    )
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_entity(self) -> CandidateMeaning:
        return CandidateMeaning(
            candidate_id=self.candidate_id,
            meaning=self.meaning,
            translation=self.translation,
            synonyms=self.synonyms,
            examples=self.examples,
            ipa=self.ipa,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(entity: CandidateMeaning) -> CandidateMeaningModel:
        return CandidateMeaningModel(
            candidate_id=entity.candidate_id,
            meaning=entity.meaning,
            translation=entity.translation,
            synonyms=entity.synonyms,
            examples=entity.examples,
            ipa=entity.ipa,
            generated_at=entity.generated_at,
        )


class CandidateMediaModel(Base):
    """SQLAlchemy model for the media enrichment of a candidate (1:1)."""

    __tablename__ = "candidate_media"

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        nullable=False,
    )
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_entity(self) -> CandidateMedia:
        return CandidateMedia(
            candidate_id=self.candidate_id,
            screenshot_path=self.screenshot_path,
            audio_path=self.audio_path,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(entity: CandidateMedia) -> CandidateMediaModel:
        return CandidateMediaModel(
            candidate_id=entity.candidate_id,
            screenshot_path=entity.screenshot_path,
            audio_path=entity.audio_path,
            start_ms=entity.start_ms,
            end_ms=entity.end_ms,
            generated_at=entity.generated_at,
        )


class CandidatePronunciationModel(Base):
    """SQLAlchemy model for pronunciation audio enrichment (1:1 with candidate)."""

    __tablename__ = "candidate_pronunciations"

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        nullable=False,
    )
    us_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uk_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_entity(self) -> CandidatePronunciation:
        return CandidatePronunciation(
            candidate_id=self.candidate_id,
            us_audio_path=self.us_audio_path,
            uk_audio_path=self.uk_audio_path,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(entity: CandidatePronunciation) -> CandidatePronunciationModel:
        return CandidatePronunciationModel(
            candidate_id=entity.candidate_id,
            us_audio_path=entity.us_audio_path,
            uk_audio_path=entity.uk_audio_path,
            generated_at=entity.generated_at,
        )


class JobModel(Base):
    """SQLAlchemy model for the job queue."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_entity(self) -> Job:
        from backend.domain.entities.job import Job
        from backend.domain.value_objects.job_status import JobStatus
        from backend.domain.value_objects.job_type import JobType

        return Job(
            id=self.id,
            job_type=JobType(self.job_type),
            candidate_id=self.candidate_id,
            source_id=self.source_id,
            status=JobStatus(self.status),
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
        )

    @staticmethod
    def from_entity(entity: Job) -> JobModel:
        return JobModel(
            id=entity.id,
            job_type=entity.job_type.value,
            candidate_id=entity.candidate_id,
            source_id=entity.source_id,
            status=entity.status.value,
            error=entity.error,
            created_at=entity.created_at,
            started_at=entity.started_at,
        )
