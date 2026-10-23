"""A long operation that cannot even begin its run still drops its lock: otherwise every
write would be refused until a restart, with nothing to show for it."""
from unittest.mock import MagicMock

import pytest
from backend.application.dto.long_operation_dtos import LongOperationOutcome
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.utils.long_operation_progress import LongOperationProgress
from backend.infrastructure.api.background_long_operation import (
    BackgroundLevelChangeLauncher,
    BackgroundLongOperationLauncher,
)


@pytest.mark.unit
def test_a_run_that_breaks_before_the_change_drops_the_lock() -> None:
    progress = LongOperationProgress()
    release = MagicMock()

    def broken_run(_request: UpdateSettingsRequest) -> None:
        raise RuntimeError("no session")

    launcher = BackgroundLongOperationLauncher(
        start=MagicMock(), release=release, progress=progress, spawn=lambda run: run(),
    )
    BackgroundLevelChangeLauncher(launcher, broken_run).start(
        UpdateSettingsRequest(cefr_level="C1"),
    )

    release.assert_called_once_with()
    assert progress.status().outcome is LongOperationOutcome.FAILED
