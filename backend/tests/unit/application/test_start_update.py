from __future__ import annotations

import pytest
from backend.application.use_cases.start_update import StartUpdateUseCase
from backend.domain.exceptions import LongOperationInProgressError, UpdateAlreadyRunningError
from backend.domain.ports.long_operation_lock import LongOperationLock
from backend.domain.value_objects.update_progress import UpdateState

from tests.release_support import FakeUpdateRunner


class _Lock(LongOperationLock):
    def __init__(self, held: bool) -> None:
        self._held = held

    def take(self) -> None:
        raise NotImplementedError

    def held(self) -> bool:
        return self._held

    def release(self) -> None:
        raise NotImplementedError


@pytest.mark.unit
def test_starts_the_update_when_nothing_runs() -> None:
    runner = FakeUpdateRunner(UpdateState.IDLE)

    StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 1


@pytest.mark.unit
@pytest.mark.parametrize("previous", [UpdateState.FAILED, UpdateState.DONE])
def test_a_finished_update_does_not_block_the_next_one(previous: UpdateState) -> None:
    runner = FakeUpdateRunner(previous)

    StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 1


@pytest.mark.unit
def test_refuses_while_a_long_operation_holds_the_lock() -> None:
    runner = FakeUpdateRunner(UpdateState.IDLE)

    with pytest.raises(LongOperationInProgressError):
        StartUpdateUseCase(_Lock(held=True), runner).execute()

    assert runner.started == 0


@pytest.mark.unit
def test_refuses_while_an_update_runs() -> None:
    runner = FakeUpdateRunner(UpdateState.RUNNING)

    with pytest.raises(UpdateAlreadyRunningError):
        StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 0
