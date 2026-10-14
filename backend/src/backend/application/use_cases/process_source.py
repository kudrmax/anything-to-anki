from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import AnalyzeTextRequest, dto_to_usage_distribution
from backend.application.dto.cefr_dtos import dto_to_breakdown
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceHasNoDocumentError,
    SourceNotFoundError,
    TopicTargetsMissingError,
)
from backend.domain.services.document_time import time_of
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.dto.analysis_dtos import WordDTO
    from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.source import Source
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)

_ALLOWED_START_STATUSES = frozenset({SourceStatus.NEW, SourceStatus.ERROR})


class ProcessSourceUseCase:
    """Orchestrates async source processing: validates, runs pipeline, saves results."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        vocabulary: UserVocabulary,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        analyze_text_use_case: AnalyzeTextUseCase,
        document_repo: DocumentRepository,
        media_repo: CandidateMediaRepository | None = None,
        topic_phrase_collector: TopicPhraseCollector | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._vocabulary = vocabulary
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver
        self._analyze_text = analyze_text_use_case
        self._document_repo = document_repo
        self._media_repo = media_repo
        self._topic_phrase_collector = topic_phrase_collector

    def start(self, source_id: int) -> None:
        """Validate source and mark as PROCESSING. Call before launching background task."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _ALLOWED_START_STATUSES:
            raise SourceAlreadyProcessedError(source_id)
        if source.role is SourceRole.TOPIC and not self._topic_ready(source_id):
            raise TopicTargetsMissingError(source_id)
        self._source_repo.update_status(source_id, SourceStatus.PROCESSING)

    def _topic_ready(self, source_id: int) -> bool:
        return (
            self._topic_phrase_collector is not None
            and self._topic_phrase_collector.has_targets(source_id)
        )

    def _notify_stage(
        self,
        source_id: int,
        stage: ProcessingStage,
        on_stage_commit: Callable[[], None] | None,
    ) -> None:
        logger.info(
            "process_source: stage transition (source_id=%d, stage=%s)",
            source_id, stage.value,
        )
        self._source_repo.update_status(
            source_id, SourceStatus.PROCESSING, processing_stage=stage,
        )
        if on_stage_commit:
            on_stage_commit()

    def execute(
        self,
        source_id: int,
        *,
        on_stage_commit: Callable[[], None] | None = None,
    ) -> None:
        """Run the full pipeline and save results. Call in background thread."""
        logger.info("process_source: execute start (source_id=%d)", source_id)
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.role is SourceRole.TOPIC:
            self._process_topic(source, on_stage_commit)
            return

        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)

        self._notify_stage(source_id, ProcessingStage.ANALYZING_TEXT, on_stage_commit)
        cefr_level = self._settings_repo.get("cefr_level", "B1") or "B1"
        request = AnalyzeTextRequest(
            user_level=cefr_level,
            vocabulary=self._vocabulary.snapshot(),
            frequent_word_zipf=self._threshold_resolver.resolve().zipf,
        )
        result = self._analyze_text.execute(document, request)

        stored = [self._stored(source_id, word) for word in result.words]
        created = self._candidate_repo.create_batch(stored)

        # A phrase of timed lines gets their time: the clip of its card
        timed = 0
        for candidate in created:
            if candidate.id is None or candidate.phrase_position is None:
                continue
            time = time_of(document, candidate.phrase_position)
            if time is None or self._media_repo is None:
                continue
            self._media_repo.upsert(CandidateMedia(
                candidate_id=candidate.id,
                screenshot_path=None,
                audio_path=None,
                start_ms=time[0],
                end_ms=time[1],
                generated_at=None,
            ))
            timed += 1
        self._source_repo.update_status(source_id, SourceStatus.DONE)
        logger.info(
            "process_source: done (source_id=%d, candidates_created=%d, with_timecodes=%d)",
            source_id, len(created), timed,
        )

    @staticmethod
    def _stored(source_id: int, word: WordDTO) -> StoredCandidate:
        # TRANSITIONAL(words-phrases): removed in Task 6 — one phrase per word, the best
        # scored occurrence (ties to the earliest), until select_phrases/plan_rebuild
        occurrence = min(word.occurrences, key=lambda o: o.fragment_score)
        return StoredCandidate(
            source_id=source_id,
            lemma=word.lemma,
            pos=word.pos,
            cefr_level=word.cefr_level,
            zipf_frequency=word.zipf_frequency,
            source_phrase=occurrence.phrase,
            occurrences=len(word.occurrences),
            is_phrasal_verb=word.is_phrasal_verb,
            status=CandidateStatus.PENDING,
            cefr_breakdown=dto_to_breakdown(word.cefr_breakdown) if word.cefr_breakdown else None,
            usage_distribution=dto_to_usage_distribution(word.usage_distribution),
            phrase_position=occurrence.phrase_position.to_position(),
            occurrence_key=occurrence.key.to_key(),
            fragment_score=occurrence.fragment_score,
        )

    def _process_topic(
        self,
        source: Source,
        on_stage_commit: Callable[[], None] | None,
    ) -> None:
        """Topics have no text to analyse: their phrases come from other sources."""
        assert source.id is not None
        if self._topic_phrase_collector is None:
            raise TopicTargetsMissingError(source.id)
        self._notify_stage(source.id, ProcessingStage.COLLECTING_PHRASES, on_stage_commit)
        collected = self._topic_phrase_collector.collect(source.id)
        created = self._candidate_repo.create_batch(collected.candidates)
        self._source_repo.update_status(source.id, SourceStatus.DONE)
        logger.info(
            "process_source: topic done (source_id=%d, candidates_created=%d)",
            source.id, len(created),
        )
