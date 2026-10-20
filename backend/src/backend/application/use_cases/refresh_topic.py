from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import TopicRefreshSummaryDTO
from backend.domain.exceptions import (
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.utils.collected_phrases import CollectedPhrases
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.new_card import NewCard

logger = logging.getLogger(__name__)


class RefreshTopicUseCase:
    """Collects a topic's phrases again and adds only what it has not got yet.

    Sources added since the topic was processed may hold real phrases for its targets; they
    are added beside the word's phrases, a generated one included. Nothing is replaced or
    removed: decisions, results and every phrase stay as they are.
    `start` takes the source inside a write its caller opens, committed before `run`, which
    frees it whatever happens.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        occurrence_repo: OccurrenceRepository,
        collected_phrases: CollectedPhrases,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        collector: TopicPhraseCollector,
    ) -> None:
        self._source_repo = source_repo
        self._occurrence_repo = occurrence_repo
        self._collected_phrases = collected_phrases
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._collector = collector

    def start(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if SourceOperationKind.REFRESH not in available_operations(source):
            raise RefreshNotSupportedError(source_id)
        if not self._lock.acquire(source_id, SourceOperationKind.REFRESH):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def execute(self, source_id: int) -> TopicRefreshSummaryDTO:
        with self._unit_of_work.write():
            self.start(source_id)
        return self.run(source_id)

    def run(self, source_id: int) -> TopicRefreshSummaryDTO:
        try:
            collected = self._collector.collect(source_id)
            with self._unit_of_work.write():
                if self._source_repo.get_by_id(source_id) is None:
                    raise SourceNotFoundError(source_id)
                summary = self._add_missing(source_id, collected)
            logger.info(
                "refresh_topic: done (source_id=%d, words_added=%d, phrases_added=%d)",
                source_id, summary.words_added, summary.phrases_added,
            )
            return summary
        finally:
            with self._unit_of_work.write():
                self._lock.release(source_id)

    def _add_missing(self, source_id: int, collected: list[NewCard]) -> TopicRefreshSummaryDTO:
        words = {w.id: w.key for w in self._occurrence_repo.word_rows(source_id)}
        texts: dict[WordKey, set[str]] = {key: set() for key in words.values()}
        for row in self._occurrence_repo.projection(source_id):
            texts[words[row.candidate_id]].add(row.text_hash)
        missing: list[NewCard] = []
        for card in collected:
            key = WordKey.of(card.word.lemma, card.word.is_phrasal_verb)
            text = OccurrenceRow.hash_text(card.phrase.text)
            if text in texts.get(key, set()):
                continue
            texts.setdefault(key, set()).add(text)
            missing.append(card)
        self._collected_phrases.add(source_id, missing)
        new_words = {WordKey.of(c.word.lemma, c.word.is_phrasal_verb) for c in missing}
        return TopicRefreshSummaryDTO(
            words_added=len(new_words - set(words.values())), phrases_added=len(missing),
        )
