from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import TopicRefreshSummaryDTO
from backend.application.utils.long_operation_runner import Applied, SourceWork
from backend.domain.exceptions import RefreshNotSupportedError, SourceNotFoundError
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.application.utils.collected_phrases import CollectedPhrases
    from backend.application.utils.long_operation_runner import (
        LongOperationRunner,
        OperationResult,
    )
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.value_objects.new_card import NewCard

logger = logging.getLogger(__name__)


class RefreshTopicUseCase:
    """Collects topics' phrases again and adds only what they have not got yet.

    Sources added since a topic was processed may hold real phrases for its targets; they
    are added beside the word's phrases, a generated one included. Nothing is replaced or
    removed: decisions, results and every phrase stay as they are. The refresh of topics is
    one long operation: `refresh` runs it once its lock is held.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        occurrence_repo: OccurrenceRepository,
        collected_phrases: CollectedPhrases,
        unit_of_work: UnitOfWork,
        collector: TopicPhraseCollector,
        runner: LongOperationRunner,
    ) -> None:
        self._source_repo = source_repo
        self._occurrence_repo = occurrence_repo
        self._collected_phrases = collected_phrases
        self._unit_of_work = unit_of_work
        self._collector = collector
        self._runner = runner

    def check(self, source_id: int) -> None:
        """Raises why the source cannot be refreshed."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if SourceOperationKind.REFRESH not in available_operations(source):
            raise RefreshNotSupportedError(source_id)

    def refresh(
        self, targets: Callable[[], list[int]],
    ) -> OperationResult[TopicRefreshSummaryDTO] | None:
        """The topics `targets` reads, refreshed together; None when cancelled."""
        return self._runner.run(_Refresh(targets, self))

    def execute(self, source_id: int) -> TopicRefreshSummaryDTO | None:
        """One topic refreshed as a long operation of its own; its failure is raised."""
        with self._unit_of_work.read():
            self.check(source_id)
        result = self.refresh(lambda: [source_id])
        if result is None:
            return None
        if result.failures:
            raise result.failures[0][1]
        [summary] = result.results
        return summary

    def collect(self, source_id: int) -> list[NewCard]:
        return self._collector.collect(source_id)

    def add_missing(self, source_id: int, collected: list[NewCard]) -> TopicRefreshSummaryDTO:
        """Inside the write: what the topic has not got yet of what was collected."""
        if self._source_repo.get_by_id(source_id) is None:
            raise SourceNotFoundError(source_id)
        summary = self._add_missing(source_id, collected)
        logger.info(
            "refresh_topic: done (source_id=%d, words_added=%d, phrases_added=%d)",
            source_id, summary.words_added, summary.phrases_added,
        )
        return summary

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


class _Refresh(SourceWork[tuple[int, list["NewCard"]], TopicRefreshSummaryDTO]):
    """A topic that fails is counted; the others are refreshed."""

    def __init__(self, targets: Callable[[], list[int]], refresh: RefreshTopicUseCase) -> None:
        self._read_targets = targets
        self._refresh = refresh

    def targets(self) -> list[int]:
        return self._read_targets()

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        return {}

    def prepare(self, source_id: int, report: PartReport) -> tuple[int, list[NewCard]]:
        collected = self._refresh.collect(source_id)
        report(1.0)
        return source_id, collected

    def apply(self, prepared: tuple[int, list[NewCard]]) -> Applied[TopicRefreshSummaryDTO]:
        source_id, collected = prepared
        return Applied(self._refresh.add_missing(source_id, collected), [])

    def failed(self, source_id: int, error: Exception) -> None:
        logger.info("refresh_topic: source %d failed: %s", source_id, error)
