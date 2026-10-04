from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.entities.ai_usage_record import AIUsageRecord


class AIUsageRepository(ABC):
    """Port for the history of AI calls."""

    @abstractmethod
    def add(self, record: AIUsageRecord) -> AIUsageRecord: ...

    @abstractmethod
    def list_between(self, start: datetime | None, end: datetime) -> list[AIUsageRecord]:
        """Records with start <= created_at < end, oldest first; no start means since the first."""

    @abstractmethod
    def first_recorded_at(self) -> datetime | None:
        """When the oldest record was made; None while there are none."""
