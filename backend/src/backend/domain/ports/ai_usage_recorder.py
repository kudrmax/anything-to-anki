from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.ai_usage_record import AIUsageRecord


class AIUsageRecorder(ABC):
    """Port that keeps a record of every AI call, independently of the caller's work."""

    @abstractmethod
    def record(self, record: AIUsageRecord) -> None: ...
