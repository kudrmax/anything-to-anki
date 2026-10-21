import pytest
from backend.application.utils.level_change_progress import LevelChangeProgress
from backend.domain.services.level_change_progress import (
    ANALYSE_SHARE,
    APPLY_SHARE,
    DONE_PERCENT,
    LevelChangeStage,
)


@pytest.mark.unit
class TestLevelChangeProgress:
    def test_idle_is_at_zero(self) -> None:
        status = LevelChangeProgress().status()
        assert (status.running, status.percent, status.cancellable) == (False, 0, False)

    def test_just_started_is_at_zero(self) -> None:
        progress = LevelChangeProgress()
        assert progress.try_start()
        assert progress.status().percent == 0

    def test_stages_go_up_to_done(self) -> None:
        progress = LevelChangeProgress()
        progress.try_start()
        progress.step(LevelChangeStage.ANALYSE, 5, 10)
        assert progress.status().percent == ANALYSE_SHARE // 2
        progress.step(LevelChangeStage.APPLY, 10, 10)
        assert progress.status().percent == ANALYSE_SHARE + APPLY_SHARE
        progress.succeed()
        assert progress.status().percent == DONE_PERCENT

    def test_a_second_start_leaves_the_running_one(self) -> None:
        progress = LevelChangeProgress()
        progress.try_start()
        progress.step(LevelChangeStage.APPLY, 1, 2)
        before = progress.status()
        assert not progress.try_start()
        assert progress.status() == before
