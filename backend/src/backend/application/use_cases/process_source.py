from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.long_operation_runner import Applied, SourceWork
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceNotFoundError,
    SourceOperationBusyError,
    TopicTargetsMissingError,
)
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.collected_phrases import CollectedPhrases
    from backend.application.utils.long_operation_runner import (
        LongOperationRunner,
        OperationResult,
    )
    from backend.application.utils.source_rebuilder import AnalysedSource, SourceRebuilder
    from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.value_objects.new_card import NewCard

logger = logging.getLogger(__name__)

_ALLOWED_START_STATUSES = frozenset({SourceStatus.NEW, SourceStatus.ERROR})
# The tail of the traceback a failed processing leaves on its source.
ERROR_DETAIL_LENGTH = 500


@dataclass(frozen=True)
class _Prepared:
    """A text source analysed, or the phrases collected for a topic."""

    source_id: int
    analysed: AnalysedSource | None
    collected: list[NewCard] | None


class ProcessSourceUseCase:
    """Processes new sources — a rebuild of a source with nothing in it yet — as one long
    operation: all of them done in one write, or none.

    `check` tells whether a source may be processed, before the operation starts. `run`
    processes, once the long operation lock is held. A source whose processing fails gets
    its error in the same write; the others are done.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        collected_phrases: CollectedPhrases,
        lock: SourceOperationLock,
        rebuilder: SourceRebuilder,
        runner: LongOperationRunner,
        topic_phrase_collector: TopicPhraseCollector | None = None,
    ) -> None:
        self._source_repo = source_repo
        self._collected_phrases = collected_phrases
        self._lock = lock
        self._rebuilder = rebuilder
        self._runner = runner
        self._topic_phrase_collector = topic_phrase_collector

    def check(self, source_id: int) -> None:
        """Raises why the source cannot be processed now."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.status not in _ALLOWED_START_STATUSES:
            raise SourceAlreadyProcessedError(source_id)
        if source.role is SourceRole.TOPIC and not self._topic_ready(source_id):
            raise TopicTargetsMissingError(source_id)
        held = self._lock.held(source_id)
        if held is not None:
            raise SourceOperationBusyError(source_id, held)

    def run(self, source_ids: Sequence[int]) -> OperationResult[None] | None:
        """Processes the sources in their order; None when cancelled or failed."""
        return self._runner.run(_Processing(
            list(source_ids), self._source_repo, self._collected_phrases, self._rebuilder,
            self._topic_phrase_collector,
        ))

    def _topic_ready(self, source_id: int) -> bool:
        return (
            self._topic_phrase_collector is not None
            and self._topic_phrase_collector.has_targets(source_id)
        )


class _Processing(SourceWork[_Prepared, None]):
    """A text source is analysed and applied as an Update of an empty source; a topic gets
    the phrases its targets have in the other sources."""

    def __init__(
        self,
        source_ids: list[int],
        source_repo: SourceRepository,
        collected_phrases: CollectedPhrases,
        rebuilder: SourceRebuilder,
        collector: TopicPhraseCollector | None,
    ) -> None:
        self._source_ids = source_ids
        self._source_repo = source_repo
        self._collected_phrases = collected_phrases
        self._rebuilder = rebuilder
        self._collector = collector

    def targets(self) -> list[int]:
        return self._source_ids

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        return self._rebuilder.sizes(source_ids)

    def prepare(self, source_id: int, report: PartReport) -> _Prepared:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.role is SourceRole.TOPIC:
            if self._collector is None:
                raise TopicTargetsMissingError(source_id)
            collected = self._collector.collect(source_id)
            report(1.0)
            return _Prepared(source_id, None, collected)
        return _Prepared(source_id, self._rebuilder.analyse(source_id, report=report), None)

    def apply(self, prepared: _Prepared) -> Applied[None]:
        if prepared.collected is not None:
            created = self._collected_phrases.add(prepared.source_id, prepared.collected)
            self._source_repo.update_status(prepared.source_id, SourceStatus.DONE)
            logger.info(
                "process_source: topic done (source_id=%d, phrases_created=%d)",
                prepared.source_id, len(created),
            )
            return Applied(None, [])
        assert prepared.analysed is not None
        applied = self._rebuilder.apply_inside(prepared.analysed, RebuildMode.UPDATE)
        logger.info(
            "process_source: done (source_id=%d, words_created=%d, phrases_created=%d)",
            prepared.source_id, len(applied.plan.words_to_create),
            len(applied.plan.occ_to_insert),
        )
        return Applied(None, applied.dropped_files)

    def failed(self, source_id: int, error: Exception) -> None:
        """The source shows the tail of what went wrong."""
        detail = "".join(traceback.format_exception(error))[-ERROR_DETAIL_LENGTH:]
        self._source_repo.update_status(source_id, SourceStatus.ERROR, error_message=detail)
