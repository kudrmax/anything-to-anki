from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.card_report import CardReport


class CardReportRepository(ABC):
    """Port for the user's complaints about cards."""

    @abstractmethod
    def add(self, report: CardReport) -> CardReport: ...

    @abstractmethod
    def list_all(self) -> list[CardReport]:
        """Newest first."""
