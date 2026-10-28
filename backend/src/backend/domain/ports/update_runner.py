from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.update_progress import UpdateProgress


class UpdateRunner(ABC):
    """Port for updating this copy: it runs apart from the app, which it restarts."""

    @abstractmethod
    def start(self) -> None:
        """Starts the update and returns at once."""

    @abstractmethod
    def state(self) -> UpdateProgress:
        """How the last update went; idle if none was started."""
