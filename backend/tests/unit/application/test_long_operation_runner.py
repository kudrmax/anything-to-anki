"""A long operation: every source prepared outside any transaction, then all applied in one
write that drops the lock; cancelled or failed, nothing is written and the lock is dropped;
the progress moves inside a source and tells how the operation ended."""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from backend.application.dto.long_operation_dtos import LongOperationOutcome
from backend.application.utils.long_operation_progress import LongOperationProgress
from backend.application.utils.long_operation_runner import (
    Applied,
    LongOperationRunner,
    SourceWork,
)
from backend.domain.ports.long_operation_lock import LongOperationLock
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.domain.services.long_operation_progress import ANALYSE_SHARE
from backend.domain.value_objects.long_operation_kind import LongOperationKind

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from backend.domain.services.long_operation_progress import PartReport


class _Lock(LongOperationLock):
    def __init__(self, log: list[str]) -> None:
        self._log = log

    def take(self) -> None:
        self._log.append("take")

    def held(self) -> bool:
        return True

    def release(self) -> None:
        self._log.append("release")


class _UnitOfWork(UnitOfWork):
    """Records what each write did, and whether it was committed."""

    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.writing = False

    @contextmanager
    def write(self) -> Iterator[None]:
        self._log.append("begin")
        self.writing = True
        try:
            yield
        except BaseException:
            self._log.append("rollback")
            raise
        finally:
            self.writing = False
        self._log.append("commit")

    @contextmanager
    def read(self) -> Iterator[None]:
        yield


class _Files:
    def __init__(self) -> None:
        self.removed: list[str] = []

    def remove(self, names: Sequence[str]) -> None:
        self.removed += names


class _Work(SourceWork[int, str]):
    """Each source prepares to its id and applies to its name; `sizes` weigh the progress."""

    def __init__(
        self,
        log: list[str],
        uow: _UnitOfWork,
        targets: list[int],
        sizes: dict[int, int] | None = None,
        on_prepare: Callable[[int, PartReport], None] | None = None,
        broken: frozenset[int] = frozenset(),
        strict: bool = False,
    ) -> None:
        self._log = log
        self._uow = uow
        self._targets = targets
        self._sizes = sizes or {}
        self._on_prepare = on_prepare
        self._broken = broken
        self._strict = strict
        self.failures: list[int] = []

    def targets(self) -> list[int]:
        return self._targets

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        return self._sizes

    def prepare(self, source_id: int, report: PartReport) -> int:
        assert not self._uow.writing, "prepared inside a transaction"
        if self._on_prepare is not None:
            self._on_prepare(source_id, report)
        if source_id in self._broken:
            raise ValueError(f"source {source_id} broke")
        self._log.append(f"prepare {source_id}")
        return source_id

    def apply_first(self) -> None:
        self._log.append("begin work")

    def apply(self, prepared: int) -> Applied[str]:
        assert self._uow.writing, "applied outside the write"
        self._log.append(f"apply {prepared}")
        return Applied(f"source {prepared}", [f"{prepared}.mp3"])

    def failed(self, source_id: int, error: Exception) -> None:
        if self._strict:
            raise error
        self._log.append(f"failed {source_id}")
        self.failures.append(source_id)


class _Bench:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.uow = _UnitOfWork(self.log)
        self.files = _Files()
        self.progress = LongOperationProgress()
        self.progress.try_start(LongOperationKind.UPDATE)
        self.runner = LongOperationRunner(_Lock(self.log), self.files, self.uow, self.progress)

    def work(self, targets: list[int], **kwargs: object) -> _Work:
        return _Work(self.log, self.uow, targets, **kwargs)  # type: ignore[arg-type]


@pytest.fixture()
def bench() -> _Bench:
    return _Bench()


def test_every_source_is_prepared_then_all_applied_in_one_write_that_drops_the_lock(
    bench: _Bench,
) -> None:
    result = bench.runner.run(bench.work([1, 2]))

    assert bench.log == [
        "prepare 1", "prepare 2",
        "begin", "begin work", "apply 1", "apply 2", "release", "commit",
    ]
    assert result is not None
    assert (result.results, result.failed) == (["source 1", "source 2"], 0)
    assert bench.files.removed == ["1.mp3", "2.mp3"]
    assert bench.progress.status().outcome is LongOperationOutcome.SUCCEEDED


def test_a_cancel_while_preparing_writes_nothing_and_drops_the_lock(bench: _Bench) -> None:
    def cancel_on_the_second(source_id: int, _report: PartReport) -> None:
        if source_id == 2:
            bench.progress.cancel()

    result = bench.runner.run(bench.work([1, 2, 3], on_prepare=cancel_on_the_second))

    assert result is None
    assert "apply 1" not in bench.log
    assert bench.log[-3:] == ["begin", "release", "commit"]
    assert bench.files.removed == []
    assert bench.progress.status().outcome is LongOperationOutcome.CANCELLED


def test_a_cancel_stops_a_big_source_where_it_is(bench: _Bench) -> None:
    reached: list[float] = []

    def long_source(_source_id: int, report: PartReport) -> None:
        for part in (0.1, 0.2, 0.3, 0.4):
            reached.append(part)
            if part == 0.2:
                bench.progress.cancel()
            report(part)

    result = bench.runner.run(bench.work([1], on_prepare=long_source))

    assert result is None
    assert reached == [0.1, 0.2]
    assert bench.progress.status().outcome is LongOperationOutcome.CANCELLED


def test_a_failure_while_applying_rolls_everything_back(bench: _Bench) -> None:
    work = bench.work([1, 2])

    def broken_apply(prepared: int) -> Applied[str]:
        if prepared == 2:
            raise RuntimeError("disk full")
        return Applied("ok", [])

    work.apply = broken_apply  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="disk full"):
        bench.runner.run(work)

    assert "rollback" in bench.log
    assert bench.log[-3:] == ["begin", "release", "commit"]
    status = bench.progress.status()
    assert (status.outcome, status.error) == (LongOperationOutcome.FAILED, "disk full")


def test_a_source_that_fails_to_prepare_is_told_inside_the_same_write(bench: _Bench) -> None:
    work = bench.work([1, 2, 3], broken=frozenset({2}))

    result = bench.runner.run(work)

    assert result is not None
    assert (result.results, result.failed) == (["source 1", "source 3"], 1)
    assert bench.log[bench.log.index("begin"):] == [
        "begin", "begin work", "apply 1", "apply 3", "failed 2", "release", "commit",
    ]


def test_a_strict_operation_fails_whole_when_one_source_fails(bench: _Bench) -> None:
    with pytest.raises(ValueError, match="source 2 broke"):
        bench.runner.run(bench.work([1, 2], broken=frozenset({2}), strict=True))

    assert "rollback" in bench.log
    assert bench.progress.status().error == "source 2 broke"


def test_the_progress_moves_inside_a_source_by_its_weight(bench: _Bench) -> None:
    seen: list[int] = []

    def report_halves(source_id: int, report: PartReport) -> None:
        report(0.5)
        seen.append(bench.progress.status().percent)
        report(1.0)

    bench.runner.run(bench.work([1, 2], sizes={1: 300, 2: 100}, on_prepare=report_halves),
    )

    assert seen == [int(ANALYSE_SHARE * 150 / 400), int(ANALYSE_SHARE * 350 / 400)]


def test_a_source_with_no_text_still_moves_the_progress(bench: _Bench) -> None:
    seen: list[int] = []

    def report_whole(_source_id: int, report: PartReport) -> None:
        report(1.0)
        seen.append(bench.progress.status().percent)

    bench.runner.run(bench.work([1, 2], on_prepare=report_whole))

    assert seen == [ANALYSE_SHARE // 2, ANALYSE_SHARE]
