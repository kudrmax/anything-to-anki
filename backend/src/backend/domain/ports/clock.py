from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class Clock(ABC):
    """Port for the current time: the one place a request or job reads `now` from."""

    @abstractmethod
    def now(self) -> datetime:
        """The current moment, timezone-aware."""
