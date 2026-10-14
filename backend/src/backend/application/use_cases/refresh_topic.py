from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import TopicRefreshSummaryDTO
from backend.domain.exceptions import (
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import available_operation
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class RefreshTopicUseCase:
    """Collects a topic's phrases again and adds only what it has not got yet.

    Sources added since the topic was processed may hold real phrases for its targets.
    Nothing the topic has is changed or removed: words, phrases, decisions and results
    stay as they are. `start` takes the source and must be committed before `run`, which
    frees it whatever happens.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        collector: TopicPhraseCollector,
        review_status: ReviewStatusUpdater,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._collector = collector
        self._review_status = review_status

    def start(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if available_operation(source) is not SourceOperationKind.REFRESH:
            raise RefreshNotSupportedError(source_id)
        if not self._lock.acquire(source_id, SourceOperationKind.REFRESH):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def execute(self, source_id: int) -> TopicRefreshSummaryDTO:
        self.start(source_id)
        self._unit_of_work.commit()
        return self.run(source_id)

    def run(self, source_id: int) -> TopicRefreshSummaryDTO:
        try:
            self._unit_of_work.commit()
            collected = self._collector.collect(source_id).candidates
            with self._unit_of_work.write():
                if self._source_repo.get_by_id(source_id) is None:
                    raise SourceNotFoundError(source_id)
                summary = self._add_missing(source_id, collected)
                self._review_status.refresh(source_id)
            logger.info(
                "refresh_topic: done (source_id=%d, words_added=%d, phrases_added=%d)",
                source_id, summary.words_added, summary.phrases_added,
            )
            return summary
        finally:
            self._unit_of_work.rollback()
            self._lock.release(source_id)
            self._unit_of_work.commit()

    def _add_missing(
        self, source_id: int, collected: list[StoredCandidate],
    ) -> TopicRefreshSummaryDTO:
        words = {w.id: w.key for w in self._occurrence_repo.word_rows(source_id)}
        texts: dict[WordKey, set[str]] = {key: set() for key in words.values()}
        for row in self._occurrence_repo.projection(source_id):
            texts[words[row.candidate_id]].add(row.text_hash)
        missing: list[StoredCandidate] = []
        for candidate in collected:
            key = WordKey.of(candidate.lemma, candidate.is_phrasal_verb)
            text = OccurrenceRow.hash_text(candidate.source_phrase.text)
            if text in texts.get(key, set()):
                continue
            texts.setdefault(key, set()).add(text)
            missing.append(candidate)
        new_words = {
            WordKey.of(c.lemma, c.is_phrasal_verb) for c in missing
        } - set(words.values())
        self._candidate_repo.create_batch(missing)
        return TopicRefreshSummaryDTO(words_added=len(new_words), phrases_added=len(missing))
