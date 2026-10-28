from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.release_dtos import UpdateStateDTO

if TYPE_CHECKING:
    from backend.domain.ports.update_runner import UpdateRunner


class GetUpdateStateUseCase:
    """How the update started from the app is going."""

    def __init__(self, runner: UpdateRunner) -> None:
        self._runner = runner

    def execute(self) -> UpdateStateDTO:
        return UpdateStateDTO.from_progress(self._runner.state())
