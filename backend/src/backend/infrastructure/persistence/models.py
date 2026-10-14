from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    or_,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.entities.ai_usage_record import AIUsageRecord
from backend.domain.entities.anki_note import AnkiNote
from backend.domain.entities.bootstrap_index_meta import BootstrapIndexMeta
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.card_report import CardReport
from backend.domain.entities.collection import Collection
from backend.domain.entities.known_word import KnownWord
from backend.domain.entities.occurrence import Occurrence, OccurrenceKey
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.topic_target import TopicTarget
from backend.domain.entities.unknown_word import UnknownWord
from backend.domain.entities.word_decision import WordDecision
from backend.domain.value_objects.ai_feature import AIFeature
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.phrase import Phrase, Word
from backend.domain.value_objects.phrase_origin import PhraseOrigin, PhraseOriginKind
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_eviction import SourceEviction
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.token_usage import TokenUsage
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.utc_datetime import UTCDateTime

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.candidate_status import CandidateStatus


def dump_position(position: DocumentPosition | None) -> str | None:
    """A position is stored as `[block, start_line, start_char, end_line, end_char]`."""
    if position is None:
        return None
    return json.dumps([
        position.block,
        position.start_line,
        position.start_char,
        position.end_line,
        position.end_char,
    ])


def load_position(stored: str | None) -> DocumentPosition | None:
    if stored is None:
        return None
    block, start_line, start_char, end_line, end_char = json.loads(stored)
    return DocumentPosition(
        block=block,
        start_line=start_line,
        start_char=start_char,
        end_line=end_line,
        end_char=end_char,
    )


def dump_phrase(phrase: Phrase | None) -> str | None:
    """Stored as `{"text", "words": [[start, end, lemma, level, zipf, content], …], "target"}`."""
    if phrase is None:
        return None
    return json.dumps({
        "text": phrase.text,
        "words": [
            [w.start, w.end, w.lemma, w.level.name, w.zipf, w.content] for w in phrase.words
        ],
        "target": list(phrase.target),
    })


def load_phrase(stored: str | None) -> Phrase | None:
    if stored is None:
        return None
    raw = json.loads(stored)
    return Phrase(
        text=raw["text"],
        words=tuple(
            Word(
                start=start, end=end, lemma=lemma, level=CEFRLevel[level], zipf=zipf,
                content=content,
            )
            for start, end, lemma, level, zipf, content in raw["words"]
        ),
        target=tuple(raw["target"]),
    )


def _required_phrase(stored: str) -> Phrase:
    phrase = load_phrase(stored)
    assert phrase is not None
    return phrase


class CollectionModel(Base):
    """SQLAlchemy model for collections: a two-level tree in manual order."""

    __tablename__ = "collections"
    __table_args__ = (
        Index(
            "uq_collections_sibling_name",
            text("coalesce(parent_id, 0)"),
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> Collection:
        return Collection(
            id=self.id,
            name=self.name,
            parent_id=self.parent_id,
            position=self.position,
            deleted_at=self.deleted_at,
            created_at=self.created_at,
        )

    @staticmethod
    def from_entity(collection: Collection) -> CollectionModel:
        return CollectionModel(
            name=collection.name,
            parent_id=collection.parent_id,
            position=collection.position,
            deleted_at=collection.deleted_at,
            created_at=collection.created_at,
        )


class CollectionEvictionModel(Base):
    """Where deleting a collection moved a source: Undo puts it back."""

    __tablename__ = "collection_evictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False,
    )
    previous_collection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    moved_to_collection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_value(self) -> SourceEviction:
        return SourceEviction(
            source_id=self.source_id,
            previous_collection_id=self.previous_collection_id,
            moved_to_collection_id=self.moved_to_collection_id,
        )


class SourceModel(Base):
    """SQLAlchemy model for text sources."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_track_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )
    format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="content", server_default="content"
    )
    topic_query: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_entity(self) -> Source:
        return Source(
            id=self.id,
            title=self.title,
            status=SourceStatus(self.status),
            source_url=self.source_url,
            error_message=self.error_message,
            processing_stage=(
                ProcessingStage(self.processing_stage) if self.processing_stage else None
            ),
            video_path=self.video_path,
            audio_track_index=self.audio_track_index,
            collection_id=self.collection_id,
            created_at=self.created_at,
            format=Format(self.format) if self.format else None,
            kind=Kind(self.kind) if self.kind else None,
            role=SourceRole(self.role),
            topic_query=self.topic_query,
        )

    @staticmethod
    def from_entity(source: Source) -> SourceModel:
        return SourceModel(
            title=source.title,
            status=source.status.value,
            source_url=source.source_url,
            video_path=source.video_path,
            audio_track_index=source.audio_track_index,
            collection_id=source.collection_id,
            created_at=source.created_at,
            format=source.format.value if source.format else None,
            kind=source.kind.value if source.kind else None,
            role=source.role.value,
            topic_query=source.topic_query,
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

    final_level, decision_method = resolve_cefr_level(priority_votes, votes)

    return CEFRBreakdown(
        final_level=final_level,
        decision_method=decision_method,
        priority_votes=priority_votes,
        votes=votes,
    )


class StoredCandidateModel(Base):
    """SQLAlchemy model for the words of a source: one per lowercase lemma and
    phrasal-verb flag. Its phrases live in `phrases` (PhraseModel)."""

    __tablename__ = "candidates"
    # Media files and enrichment are keyed by candidate id — an id must never
    # be handed out twice, which plain SQLite rowids do after deletions.
    __table_args__ = (
        Index(
            "ux_candidates_word",
            "source_id",
            text("lower(lemma)"),
            "is_phrasal_verb",
            unique=True,
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str] = mapped_column(String(10), nullable=False)
    zipf_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    is_sweet_spot: Mapped[bool] = mapped_column(nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    is_phrasal_verb: Mapped[bool] = mapped_column(nullable=False, default=False)
    usage_distribution_json: Mapped[str | None] = mapped_column(
        "usage_distribution", Text, nullable=True
    )
    origin_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    origin_title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    cefr_breakdown: Mapped[CEFRBreakdownModel | None] = relationship(
        "CEFRBreakdownModel", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    # TRANSITIONAL(words-phrases): removed in Task 10
    def to_entity(self, primary: PhraseModel, status: CandidateStatus) -> StoredCandidate:
        """The word seen through its primary phrase, WITHOUT results — the repository
        attaches those."""
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
            source_phrase=_required_phrase(primary.source_phrase),
            occurrences=self.occurrences,
            is_phrasal_verb=self.is_phrasal_verb,
            status=status,
            meaning=None,
            media=None,
            cefr_breakdown=bd,
            usage_distribution=ud,
            origin=self._origin(),
            polished_phrase=load_phrase(primary.polished_phrase),
            polish_reverted=primary.polish_reverted,
            phrase_position=load_position(primary.phrase_position),
        )

    def _origin(self) -> PhraseOrigin | None:
        if self.origin_kind is None:
            return None
        return PhraseOrigin(
            kind=PhraseOriginKind(self.origin_kind), source_title=self.origin_title,
        )

    @staticmethod
    def from_entity(candidate: StoredCandidate) -> StoredCandidateModel:
        """The word of a candidate; its phrase is stored separately."""
        model = StoredCandidateModel(
            source_id=candidate.source_id,
            lemma=candidate.lemma,
            pos=candidate.pos,
            zipf_frequency=candidate.zipf_frequency,
            is_sweet_spot=candidate.is_sweet_spot,
            occurrences=candidate.occurrences,
            is_phrasal_verb=candidate.is_phrasal_verb,
            status=candidate.status.value,
            origin_kind=candidate.origin.kind.value if candidate.origin else None,
            origin_title=candidate.origin.source_title if candidate.origin else None,
        )
        if candidate.cefr_breakdown is not None:
            model.cefr_breakdown = _breakdown_to_model(candidate.cefr_breakdown)
        if candidate.usage_distribution is not None:
            dist = candidate.usage_distribution.to_dict()
            model.usage_distribution_json = json.dumps(dist) if dist else None
        return model


class PhraseModel(Base):
    """SQLAlchemy model for the phrases of a word: an occurrence of it in the text."""

    __tablename__ = "phrases"
    __table_args__ = (
        Index(
            "ux_phrases_auto_key",
            "candidate_id",
            "block",
            "line",
            "char",
            unique=True,
            sqlite_where=text("origin = 'auto'"),
        ),
        Index(
            "ux_phrases_decision",
            "candidate_id",
            unique=True,
            sqlite_where=text("is_decision = 1"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    block: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_phrase: Mapped[str] = mapped_column(Text, nullable=False)
    phrase_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    polished_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    polish_reverted: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0",
    )
    fragment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    shown_by: Mapped[str | None] = mapped_column(String(10), nullable=True)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    skipped: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    is_decision: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    decision_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    edited_by_user: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    @property
    def shown_text(self) -> str:
        """The stored phrase the card shows: the polished one unless it was reverted."""
        if self.polished_phrase is not None and not self.polish_reverted:
            return self.polished_phrase
        return self.source_phrase

    def key(self) -> OccurrenceKey | None:
        if self.block is None or self.line is None or self.char is None:
            return None
        return OccurrenceKey(block=self.block, line=self.line, char=self.char)

    def to_entity(self) -> Occurrence:
        """The phrase WITHOUT results, export and job marks — the repository attaches them."""
        return Occurrence(
            id=self.id,
            candidate_id=self.candidate_id,
            origin=OccurrenceOrigin(self.origin),
            source_phrase=_required_phrase(self.source_phrase),
            phrase_position=load_position(self.phrase_position),
            key=self.key(),
            fragment_score=self.fragment_score,
            revision=self.revision,
            shown_by=ShownBy(self.shown_by) if self.shown_by is not None else None,
            skipped=self.skipped,
            is_decision=self.is_decision,
            decision_kind=(
                DecisionKind(self.decision_kind) if self.decision_kind is not None else None
            ),
            edited_by_user=self.edited_by_user,
            polished_phrase=load_phrase(self.polished_phrase),
            polish_reverted=self.polish_reverted,
        )

    @staticmethod
    def from_entity(occurrence: Occurrence) -> PhraseModel:
        key = occurrence.key
        return PhraseModel(
            candidate_id=occurrence.candidate_id,
            block=key.block if key else None,
            line=key.line if key else None,
            char=key.char if key else None,
            source_phrase=dump_phrase(occurrence.source_phrase),
            phrase_position=dump_position(occurrence.phrase_position),
            polished_phrase=dump_phrase(occurrence.polished_phrase),
            polish_reverted=occurrence.polish_reverted,
            fragment_score=occurrence.fragment_score,
            revision=occurrence.revision,
            shown_by=occurrence.shown_by.value if occurrence.shown_by else None,
            origin=occurrence.origin.value,
            skipped=occurrence.skipped,
            is_decision=occurrence.is_decision,
            decision_kind=occurrence.decision_kind.value if occurrence.decision_kind else None,
            edited_by_user=occurrence.edited_by_user,
        )


class PhraseWordModel(Base):
    """The lemmas of the words a phrase shows: which phrases a change of knowledge touches."""

    __tablename__ = "phrase_words"
    __table_args__ = (Index("ix_phrase_words_lemma", "lemma", "phrase_id"),)

    phrase_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("phrases.id", ondelete="CASCADE"), primary_key=True,
    )
    lemma: Mapped[str] = mapped_column(String(100), primary_key=True)


class AnkiNoteModel(Base):
    """A note exported to Anki: one per note, whatever happens to its source."""

    __tablename__ = "anki_notes"

    note_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str | None] = mapped_column(String(10), nullable=True)
    matured_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_entity(self) -> AnkiNote:
        return AnkiNote(
            note_id=self.note_id,
            lemma=self.lemma,
            pos=self.pos,
            matured_at=self.matured_at,
            deleted_at=self.deleted_at,
        )


class DocumentParseModel(Base):
    """A cached parse of a document by one version of the analyzer."""

    __tablename__ = "document_parses"

    document_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    analyzer_version: Mapped[str] = mapped_column(String(60), primary_key=True)
    tokens: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )


class SourceOperationModel(Base):
    """The long operation a source is busy with; at most one per source."""

    __tablename__ = "source_operations"

    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True,
        autoincrement=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class KnownWordRemovalModel(Base):
    """A lemma the user removed from Known: Anki maturity never puts it back."""

    __tablename__ = "known_word_removals"

    lemma: Mapped[str] = mapped_column(String(100), primary_key=True)
    removed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class TopicTargetModel(Base):
    """SQLAlchemy model for targets generated for a topic source."""

    __tablename__ = "topic_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    phrase: Mapped[str] = mapped_column(String(100), nullable=False)
    example: Mapped[str] = mapped_column(Text, nullable=False)

    def to_entity(self) -> TopicTarget:
        return TopicTarget(
            id=self.id,
            source_id=self.source_id,
            position=self.position,
            phrase=self.phrase,
            example=self.example,
        )

    @staticmethod
    def from_entity(target: TopicTarget) -> TopicTargetModel:
        return TopicTargetModel(
            source_id=target.source_id,
            position=target.position,
            phrase=target.phrase,
            example=target.example,
        )


class KnownWordModel(Base):
    """SQLAlchemy model for known-word whitelist."""

    __tablename__ = "known_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    pos: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    __table_args__ = (UniqueConstraint("lemma", "pos", name="uq_known_word_lemma_pos"),)

    def to_entity(self) -> KnownWord:
        return KnownWord(
            id=self.id,
            lemma=self.lemma,
            pos=self.pos,
            created_at=self.created_at,
        )


class UnknownWordModel(Base):
    """SQLAlchemy model for the words the user said they don't know."""

    __tablename__ = "unknown_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> UnknownWord:
        return UnknownWord(id=self.id, lemma=self.lemma, created_at=self.created_at)


class WordDecisionModel(Base):
    """SQLAlchemy model for the user's verdicts on words."""

    __tablename__ = "word_decisions"

    lemma: Mapped[str] = mapped_column(String(100), primary_key=True)
    zipf_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    is_known: Mapped[bool] = mapped_column(nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> WordDecision:
        return WordDecision(
            lemma=self.lemma, zipf_frequency=self.zipf_frequency, is_known=self.is_known,
        )


class CardReportModel(Base):
    """SQLAlchemy model for complaints about cards.

    No foreign keys: a report outlives its candidate and source.
    """

    __tablename__ = "card_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_title: Mapped[str] = mapped_column(String(200), nullable=False)
    candidate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    phrase_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lemma: Mapped[str] = mapped_column(String(100), nullable=False)
    surface_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_fragment: Mapped[str] = mapped_column(Text, nullable=False)
    zipf_frequency: Mapped[float] = mapped_column(Float, nullable=False)
    cefr_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fragment_unknown_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_phrasal_verb: Mapped[bool] = mapped_column(nullable=False)
    reasons: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    text_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=lambda: datetime.now(tz=UTC)
    )

    def to_entity(self) -> CardReport:
        return CardReport(
            id=self.id,
            source_id=self.source_id,
            source_title=self.source_title,
            candidate_id=self.candidate_id,
            phrase_id=self.phrase_id,
            lemma=self.lemma,
            surface_form=self.surface_form,
            context_fragment=self.context_fragment,
            zipf_frequency=self.zipf_frequency,
            cefr_level=self.cefr_level,
            fragment_unknown_count=self.fragment_unknown_count,
            is_phrasal_verb=self.is_phrasal_verb,
            reasons=tuple(json.loads(self.reasons)),
            comment=self.comment,
            text_before=self.text_before,
            text_after=self.text_after,
            created_at=self.created_at,
        )


class SettingModel(Base):
    """SQLAlchemy model for application settings (key-value)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)


class AnkiSyncedCardModel(Base):
    """SQLAlchemy model for tracking phrases successfully exported to Anki.

    A word may have several rows (words merged from duplicates); the record outlives
    its phrase (`phrase_id` becomes NULL)."""

    __tablename__ = "anki_synced_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    phrase_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("phrases.id", ondelete="SET NULL"), nullable=True, unique=True,
    )
    anki_note_id: Mapped[int] = mapped_column(Integer, nullable=False)


class CandidateMeaningModel(Base):
    """SQLAlchemy model for the meaning of a phrase (1:1).

    The IPA of the word lives in `candidate_pronunciations`."""

    __tablename__ = "candidate_meanings"

    phrase_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("phrases.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_entity(self, candidate_id: int, ipa: str | None) -> CandidateMeaning:
        return CandidateMeaning(
            candidate_id=candidate_id,
            meaning=self.meaning,
            translation=self.translation,
            synonyms=self.synonyms,
            examples=self.examples,
            ipa=ipa,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(phrase_id: int, entity: CandidateMeaning) -> CandidateMeaningModel:
        return CandidateMeaningModel(
            phrase_id=phrase_id,
            meaning=entity.meaning,
            translation=entity.translation,
            synonyms=entity.synonyms,
            examples=entity.examples,
            generated_at=entity.generated_at,
        )


class CandidateMediaModel(Base):
    """SQLAlchemy model for the media enrichment of a candidate (1:1)."""

    __tablename__ = "candidate_media"

    phrase_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("phrases.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_entity(self, candidate_id: int) -> CandidateMedia:
        return CandidateMedia(
            candidate_id=candidate_id,
            screenshot_path=self.screenshot_path,
            audio_path=self.audio_path,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(phrase_id: int, entity: CandidateMedia) -> CandidateMediaModel:
        return CandidateMediaModel(
            phrase_id=phrase_id,
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
        ForeignKey("candidates.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    us_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uk_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @classmethod
    def is_generated(cls) -> ColumnElement[bool]:
        """The recordings were looked for: any row but one holding only the IPA."""
        return or_(
            cls.generated_at.is_not(None),
            cls.us_audio_path.is_not(None),
            cls.uk_audio_path.is_not(None),
            cls.ipa.is_(None),
        )

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


class CandidateTTSModel(Base):
    """SQLAlchemy model for TTS audio enrichment (1:1 with candidate)."""

    __tablename__ = "candidate_tts"

    phrase_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("phrases.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_entity(self, candidate_id: int) -> CandidateTTS:
        return CandidateTTS(
            candidate_id=candidate_id,
            audio_path=self.audio_path,
            generated_at=self.generated_at,
        )

    @staticmethod
    def from_entity(phrase_id: int, entity: CandidateTTS) -> CandidateTTSModel:
        return CandidateTTSModel(
            phrase_id=phrase_id,
            audio_path=entity.audio_path,
            generated_at=entity.generated_at,
        )


class CandidateClozeModel(Base):
    """SQLAlchemy model for the user's cloze markup (1:1 with candidate)."""

    __tablename__ = "candidate_clozes"

    phrase_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("phrases.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    hidden_word_indices: Mapped[str] = mapped_column(Text, nullable=False)
    hint_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    custom_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    phrase: Mapped[str] = mapped_column(Text, nullable=False)

    def to_entity(self, candidate_id: int) -> CandidateCloze:
        return CandidateCloze(
            candidate_id=candidate_id,
            hidden_word_indices=tuple(json.loads(self.hidden_word_indices)),
            hint_kind=ClozeHintKind(self.hint_kind),
            custom_hint=self.custom_hint,
            phrase=self.phrase,
        )

    @staticmethod
    def from_entity(phrase_id: int, entity: CandidateCloze) -> CandidateClozeModel:
        return CandidateClozeModel(
            phrase_id=phrase_id,
            hidden_word_indices=json.dumps(list(entity.hidden_word_indices)),
            hint_kind=entity.hint_kind.value,
            custom_hint=entity.custom_hint,
            phrase=entity.phrase,
        )


class CandidateMeaningImageModel(Base):
    """SQLAlchemy model for the meaning image of a candidate (1:1)."""

    __tablename__ = "candidate_meaning_images"

    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)

    def to_entity(self) -> CandidateMeaningImage:
        return CandidateMeaningImage(candidate_id=self.candidate_id, image_path=self.image_path)

    @staticmethod
    def from_entity(entity: CandidateMeaningImage) -> CandidateMeaningImageModel:
        return CandidateMeaningImageModel(
            candidate_id=entity.candidate_id, image_path=entity.image_path,
        )


class SourceDocumentModel(Base):
    """SQLAlchemy model for the document of a source (1:1), stored as JSON."""

    __tablename__ = "source_documents"

    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    document: Mapped[str] = mapped_column(Text, nullable=False)


class EnrichmentCacheModel(Base):
    """Temporary cache for enrichment data during source reprocessing."""

    __tablename__ = "enrichment_cache"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    lemma: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)
    pos: Mapped[str] = mapped_column(String(10), primary_key=True, nullable=False)
    context_fragment: Mapped[str] = mapped_column(Text, primary_key=True, nullable=False)
    # meaning
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meaning_generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # media
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # pronunciation
    us_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uk_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pronunciation_generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # tts
    tts_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    meaning_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    phrase_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("phrases.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    phrase_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    def to_entity(self) -> Job:
        from backend.domain.entities.job import Job
        from backend.domain.value_objects.job_status import JobStatus
        from backend.domain.value_objects.job_type import JobType

        return Job(
            id=self.id,
            job_type=JobType(self.job_type),
            candidate_id=self.candidate_id,
            source_id=self.source_id,
            phrase_id=self.phrase_id,
            phrase_revision=self.phrase_revision,
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
            phrase_id=entity.phrase_id,
            phrase_revision=entity.phrase_revision,
            status=entity.status.value,
            error=entity.error,
            created_at=entity.created_at,
            started_at=entity.started_at,
        )


class BootstrapIndexMetaModel(Base):
    """SQLAlchemy model for bootstrap calibration metadata."""

    __tablename__ = "bootstrap_index_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_entity(self) -> BootstrapIndexMeta:
        from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus
        return BootstrapIndexMeta(
            status=BootstrapIndexStatus(self.status),
            error=self.error,
            built_at=self.built_at,
            word_count=self.word_count,
        )


class BootstrapWordCellModel(Base):
    """SQLAlchemy model for bootstrap calibration word entries."""

    __tablename__ = "bootstrap_word_cell"

    lemma: Mapped[str] = mapped_column(String(100), primary_key=True)
    cefr_level: Mapped[str] = mapped_column(String(2), primary_key=True)
    zipf_value: Mapped[float] = mapped_column(Float, nullable=False)

    def to_entity(self) -> BootstrapWordEntry:
        from backend.domain.value_objects.cefr_level import CEFRLevel
        return BootstrapWordEntry(
            lemma=self.lemma,
            cefr_level=CEFRLevel.from_str(self.cefr_level),
            zipf_value=self.zipf_value,
        )


class AIUsageModel(Base):
    """SQLAlchemy model for the history of AI calls and the tokens they consumed."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(nullable=False)

    @classmethod
    def from_entity(cls, record: AIUsageRecord) -> AIUsageModel:
        return cls(
            created_at=record.created_at,
            feature=record.feature.value,
            model=record.model,
            input_tokens=record.usage.input_tokens,
            output_tokens=record.usage.output_tokens,
            cache_read_tokens=record.usage.cache_read_tokens,
            cache_creation_tokens=record.usage.cache_creation_tokens,
            item_count=record.item_count,
            duration_ms=record.duration_ms,
            succeeded=record.succeeded,
        )

    def to_entity(self) -> AIUsageRecord:
        return AIUsageRecord(
            id=self.id,
            created_at=self.created_at,
            feature=AIFeature(self.feature),
            model=self.model,
            usage=TokenUsage(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                cache_read_tokens=self.cache_read_tokens,
                cache_creation_tokens=self.cache_creation_tokens,
            ),
            item_count=self.item_count,
            duration_ms=self.duration_ms,
            succeeded=self.succeeded,
        )
