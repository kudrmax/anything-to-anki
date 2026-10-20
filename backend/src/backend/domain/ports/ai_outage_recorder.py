from __future__ import annotations

from abc import ABC, abstractmethod


class AIOutageRecorder(ABC):
    """Port that keeps the AI's availability as every AI call finds it,
    independently of the caller's work."""

    @abstractmethod
    def unavailable(self, reason: str) -> None: ...

    @abstractmethod
    def answered(self) -> None: ...
