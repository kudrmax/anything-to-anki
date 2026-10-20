from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceNotFoundError,
    SourceOperationBusyError,
    TopicTargetsMissingError,
)
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.utils.collected_phrases import CollectedPhrases
    from backend.application.utils.source_rebuilder import SourceRebuilder
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.entities.source import Source
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

_ALLOWED_START_STATUSES = frozenset({SourceStatus.NEW, SourceStatus.ERROR})


class ProcessSourceUseCase:
    """Processes a new source: a rebuild of a source with nothing in it yet.

    `start` takes the source in a write of its own before `execute`, which frees it
    whatever happens. The source's status stays its last outcome meanwhile: the lock is
    what shows it is being processed and keeps other operations off it.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        collected_phrases: CollectedPhrases,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        rebuilder: SourceRebuilder,
        topic_phrase_collector: TopicPhraseCollector | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._collected_phrases = collected_phrases
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._rebuilder = rebuilder
        self._topic_phrase_collector = topic_phrase_collector

    def start(self, source_id: int) -> None:
        """Validate the source and take it. Call before launching the background task."""
        with self._unit_of_work.write():
            self.take(source_id)

    def take(self, source_id: int) -> None:
        """`start` for a use case that holds the write transaction itself."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _ALLOWED_START_STATUSES:
            raise SourceAlreadyProcessedError(source_id)
        if source.role is SourceRole.TOPIC and not self._topic_ready(source_id):
            raise TopicTargetsMissingError(source_id)
        if not self._lock.acquire(source_id, SourceOperationKind.PROCESS):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def _topic_ready(self, source_id: int) -> bool:
        return (
            self._topic_phrase_collector is not None
            and self._topic_phrase_collector.has_targets(source_id)
        )

    def _notify_stage(self, source_id: int, stage: ProcessingStage) -> None:
        """Shown at once; no transaction stays open into the work of the stage."""
        logger.info(
            "process_source: stage transition (source_id=%d, stage=%s)",
            source_id, stage.value,
        )
        with self._unit_of_work.write():
            self._lock.set_stage(source_id, stage)

    def execute(self, source_id: int) -> None:
        """Run the pipeline and save the results. Call in a background thread."""
        logger.info("process_source: execute start (source_id=%d)", source_id)
        try:
            source = self._source_repo.get_by_id(source_id)
            if source is None:
                raise SourceNotFoundError(source_id)
            if source.role is SourceRole.TOPIC:
                self._process_topic(source)
                return
            self._notify_stage(source_id, ProcessingStage.ANALYZING_TEXT)
            plan = self._rebuilder.apply(self._rebuilder.analyse(source_id), RebuildMode.UPDATE)
        except BaseException:
            self._release(source_id)
            raise
        self._release(source_id)
        logger.info(
            "process_source: done (source_id=%d, words_created=%d, phrases_created=%d)",
            source_id, len(plan.words_to_create), len(plan.occ_to_insert),
        )

    def fail(self, source_id: int, error: str, *, never_ran: bool) -> None:
        """The processing failed with `error`: the source shows it. A source whose
        `execute` never ran is still taken by `start`, and is freed here."""
        with self._unit_of_work.write():
            if never_ran:
                self._lock.release(source_id)
            self._source_repo.update_status(source_id, SourceStatus.ERROR, error_message=error)

    def _release(self, source_id: int) -> None:
        with self._unit_of_work.write():
            self._lock.release(source_id)

    def _process_topic(self, source: Source) -> None:
        """Topics have no text to analyse: their phrases come from other sources. The source
        is done and free in the same write."""
        assert source.id is not None
        if self._topic_phrase_collector is None:
            raise TopicTargetsMissingError(source.id)
        self._notify_stage(source.id, ProcessingStage.COLLECTING_PHRASES)
        collected = self._topic_phrase_collector.collect(source.id)
        with self._unit_of_work.write():
            created = self._collected_phrases.add(source.id, collected)
            self._source_repo.update_status(source.id, SourceStatus.DONE)
            self._lock.release(source.id)
        logger.info(
            "process_source: topic done (source_id=%d, phrases_created=%d)",
            source.id, len(created),
        )
