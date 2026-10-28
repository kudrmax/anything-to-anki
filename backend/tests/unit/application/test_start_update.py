from __future__ import annotations

import pytest
from backend.application.use_cases.start_update import StartUpdateUseCase
from backend.domain.exceptions import LongOperationInProgressError, UpdateAlreadyRunningError
from backend.domain.ports.long_operation_lock import LongOperationLock
from backend.domain.ports.update_runner import UpdateRunner
from backend.domain.value_objects.update_progress import UpdateProgress, UpdateState


class _Lock(LongOperationLock):
    def __init__(self, held: bool) -> None:
        self._held = held

    def take(self) -> None:
        raise NotImplementedError

    def held(self) -> bool:
        return self._held

    def release(self) -> None:
        raise NotImplementedError


class _Runner(UpdateRunner):
    def __init__(self, state: UpdateState) -> None:
        self._state = state
        self.started = 0

    def start(self) -> None:
        self.started += 1

    def state(self) -> UpdateProgress:
        return UpdateProgress(self._state)


@pytest.mark.unit
def test_starts_the_update_when_nothing_runs() -> None:
    runner = _Runner(UpdateState.IDLE)

    StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 1


@pytest.mark.unit
@pytest.mark.parametrize("previous", [UpdateState.FAILED, UpdateState.DONE])
def test_a_finished_update_does_not_block_the_next_one(previous: UpdateState) -> None:
    runner = _Runner(previous)

    StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 1


@pytest.mark.unit
def test_refuses_while_a_long_operation_holds_the_lock() -> None:
    runner = _Runner(UpdateState.IDLE)

    with pytest.raises(LongOperationInProgressError):
        StartUpdateUseCase(_Lock(held=True), runner).execute()

    assert runner.started == 0


@pytest.mark.unit
def test_refuses_while_an_update_runs() -> None:
    runner = _Runner(UpdateState.RUNNING)

    with pytest.raises(UpdateAlreadyRunningError):
        StartUpdateUseCase(_Lock(held=False), runner).execute()

    assert runner.started == 0
