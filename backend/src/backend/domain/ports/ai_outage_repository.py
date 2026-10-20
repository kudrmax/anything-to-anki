from __future__ import annotations

from abc import ABC, abstractmethod


class AIOutageRepository(ABC):
    """Port for the one current outage of the AI, if any: why the AI answers nothing."""

    @abstractmethod
    def reason(self) -> str | None:
        """Why the AI is unavailable, as the AI proxy said it; None while it answers."""

    @abstractmethod
    def report(self, reason: str) -> None: ...

    @abstractmethod
    def clear(self) -> None:
        """The AI answers again."""
