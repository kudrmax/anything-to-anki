import pytest
from backend.application.utils.long_operation_progress import LongOperationProgress
from backend.domain.services.long_operation_progress import (
    ANALYSE_SHARE,
    APPLY_SHARE,
    DONE_PERCENT,
    LongOperationStage,
)
from backend.domain.value_objects.long_operation_kind import LongOperationKind

KIND = LongOperationKind.UPDATE


@pytest.mark.unit
class TestLongOperationProgress:
    def test_idle_is_at_zero(self) -> None:
        status = LongOperationProgress().status()
        assert (status.running, status.percent, status.cancellable) == (False, 0, False)

    def test_just_started_is_at_zero(self) -> None:
        progress = LongOperationProgress()
        assert progress.try_start(KIND)
        assert progress.status().percent == 0

    def test_stages_go_up_to_done(self) -> None:
        progress = LongOperationProgress()
        progress.try_start(KIND)
        progress.step(LongOperationStage.ANALYSE, 0.5)
        assert progress.status().percent == ANALYSE_SHARE // 2
        progress.step(LongOperationStage.APPLY, 1.0)
        assert progress.status().percent == ANALYSE_SHARE + APPLY_SHARE
        progress.succeed()
        assert progress.status().percent == DONE_PERCENT

    def test_a_second_start_leaves_the_running_one(self) -> None:
        progress = LongOperationProgress()
        progress.try_start(KIND)
        progress.step(LongOperationStage.APPLY, 0.5)
        before = progress.status()
        assert not progress.try_start(KIND)
        assert progress.status() == before

    def test_the_status_tells_the_kind_of_the_last_operation(self) -> None:
        progress = LongOperationProgress()
        assert progress.status().kind is None
        progress.try_start(LongOperationKind.PROCESS)
        assert progress.status().kind is LongOperationKind.PROCESS

    def test_a_part_of_a_stage_moves_the_percent_within_it(self) -> None:
        progress = LongOperationProgress()
        progress.try_start(KIND)
        progress.step(LongOperationStage.ANALYSE, 0.01)
        first = progress.status().percent
        progress.step(LongOperationStage.ANALYSE, 0.03)
        assert progress.status().percent > first

    def test_each_started_operation_has_a_new_id(self) -> None:
        progress = LongOperationProgress()
        first = progress.status().operation_id
        progress.try_start(KIND)
        progress.succeed()
        assert progress.status().operation_id == first + 1
        progress.try_start(KIND)
        assert progress.status().operation_id == first + 2
