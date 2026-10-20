from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.ai_outage import AIOutage


class AIOutageRepository(ABC):
    """Port for the one current outage of the AI, if any."""

    @abstractmethod
    def get(self) -> AIOutage | None: ...

    @abstractmethod
    def report(self, reason: str) -> None:
        """The AI is unavailable for this reason; an ongoing outage keeps its start."""

    @abstractmethod
    def clear(self) -> None:
        """The AI answers again."""
