from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.dto.settings_dtos import UpdateSettingsRequest


class LevelChangeLauncher(ABC):
    """Port for starting a level change that goes on after the request."""

    @abstractmethod
    def start(self, request: UpdateSettingsRequest) -> None:
        """Takes the lock, or raises why the change cannot start; then returns at once
        while the change runs."""
