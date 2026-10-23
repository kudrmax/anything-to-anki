from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import LongOperationCancelledError
from backend.domain.services.long_operation_progress import LongOperationStage, part_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.long_operation_progress import LongOperationProgress
    from backend.domain.ports.long_operation_lock import LongOperationLock
    from backend.domain.ports.media_files import MediaFiles
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.long_operation_progress import PartReport

logger = logging.getLogger(__name__)

RELEASE_ATTEMPTS = 3
# The weight in the progress of a source with no text of its own, such as a topic.
NO_TEXT_WEIGHT = 1


@dataclass(frozen=True)
class Applied[R]:
    """What applying one source gave, and the files of what it dropped."""

    result: R
    dropped_files: list[str]


@dataclass(frozen=True)
class OperationResult[R]:
    """The results of the sources applied, in their order, and the sources that failed with
    their errors."""

    results: list[R]
    failures: list[tuple[int, Exception]]

    @property
    def failed(self) -> int:
        return len(self.failures)


class SourceWork[P, R](ABC):
    """What one long operation does to each of its sources: prepared outside any
    transaction, then applied inside the one write of the operation."""

    @abstractmethod
    def targets(self) -> list[int]:
        """The sources, in the order they are prepared and applied; read in a read
        transaction."""

    @abstractmethod
    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        """How much there is to do for each source, as the length of its text; read in the
        same read transaction. A source left out weighs NO_TEXT_WEIGHT."""

    @abstractmethod
    def prepare(self, source_id: int, report: PartReport) -> P:
        """Everything that takes long, outside any transaction; `report` is told the share
        of the source done."""

    @abstractmethod
    def apply(self, prepared: P) -> Applied[R]:
        """Inside the write of the operation."""

    def apply_first(self) -> None:  # noqa: B027 — an optional step: most write nothing first
        """Inside the write, before any source is applied."""

    def failed(self, source_id: int, error: Exception) -> None:
        """A source whose preparation failed, inside the write after every source is
        applied. By default the whole operation fails with its error."""
        raise error


class LongOperationRunner:
    """Runs a long operation once its lock is held: nothing else writes meanwhile.

    Every source is prepared first, outside any transaction, then everything is applied in
    one write that drops the lock too: all of it or none. Cancelled, failed or cut off by a
    crash, nothing is written; the lock is dropped, and a lock a crash left behind goes at
    the next start. Files of what the operation dropped go once it is committed. The
    progress tells how far it is and how it ended; a failure is raised on as well.
    """

    def __init__(
        self,
        lock: LongOperationLock,
        media_files: MediaFiles,
        unit_of_work: UnitOfWork,
        progress: LongOperationProgress,
    ) -> None:
        self._lock = lock
        self._media_files = media_files
        self._unit_of_work = unit_of_work
        self._progress = progress

    def run[P, R](self, work: SourceWork[P, R]) -> OperationResult[R] | None:
        """The result once committed; None when cancelled. A failure is raised once the
        lock is dropped."""
        try:
            with self._unit_of_work.read():
                source_ids = work.targets()
                sizes = work.sizes(source_ids)
            prepared, failures = self._prepare_all(source_ids, sizes, work)
            result, dropped_files = self._apply_all(work, prepared, failures)
        except LongOperationCancelledError:
            logger.info("long operation: cancelled, nothing changed")
            self._release()
            self._progress.cancelled()
            return None
        except Exception as e:
            logger.exception("long operation: failed, nothing changed")
            self._release()
            self._progress.fail(str(e))
            raise
        self._remove(dropped_files)
        self._progress.succeed()
        logger.info(
            "long operation: done (applied=%d, failed=%d)", len(result.results), result.failed,
        )
        return result

    def _prepare_all[P, R](
        self, source_ids: Sequence[int], sizes: dict[int, int], work: SourceWork[P, R],
    ) -> tuple[list[P], list[tuple[int, Exception]]]:
        weights = [
            max(sizes.get(source_id, NO_TEXT_WEIGHT), NO_TEXT_WEIGHT)
            for source_id in source_ids
        ]
        total = sum(weights)
        prepared: list[P] = []
        failures: list[tuple[int, Exception]] = []
        before = 0
        for source_id, weight in zip(source_ids, weights, strict=True):
            self._progress.check_cancel()
            report = self._report(before, weight, total)
            try:
                prepared.append(work.prepare(source_id, report))
            except LongOperationCancelledError:
                raise
            except Exception as e:
                logger.exception("long operation: source %d failed", source_id)
                failures.append((source_id, e))
            before += weight
        return prepared, failures

    def _report(self, before: int, weight: int, total: int) -> PartReport:
        """The source's share done, as the share of the stage; a cancel asked for stops the
        source where it is."""

        def report(part: float) -> None:
            self._progress.step(LongOperationStage.ANALYSE, (before + weight * part) / total)
            self._progress.check_cancel()

        return report

    def _apply_all[P, R](
        self,
        work: SourceWork[P, R],
        prepared: list[P],
        failures: list[tuple[int, Exception]],
    ) -> tuple[OperationResult[R], list[str]]:
        results: list[R] = []
        dropped_files: list[str] = []
        with self._unit_of_work.write():
            work.apply_first()
            for done, item in enumerate(prepared):
                self._progress.check_cancel()
                self._progress.step(LongOperationStage.APPLY, part_of(done, len(prepared)))
                applied = work.apply(item)
                results.append(applied.result)
                dropped_files += applied.dropped_files
            for source_id, error in failures:
                work.failed(source_id, error)
            self._progress.enter_finish()
            self._lock.release()
        return OperationResult(results, failures), dropped_files

    def _remove(self, dropped_files: list[str]) -> None:
        """The operation is committed: files left behind only take room, they undo
        nothing."""
        try:
            self._media_files.remove(dropped_files)
        except OSError:
            logger.exception("long operation: files of dropped phrases left behind")

    def _release(self) -> None:
        """A lock left behind would keep every write out until the app restarts."""
        for attempt in range(1, RELEASE_ATTEMPTS + 1):
            try:
                with self._unit_of_work.write():
                    self._lock.release()
            except Exception:
                logger.exception(
                    "long operation: its lock could not be dropped (attempt %d of %d)",
                    attempt, RELEASE_ATTEMPTS,
                )
            else:
                return
