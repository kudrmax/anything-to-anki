from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation


class CandidatePronunciationRepository(ABC):
    """Port for persisting pronunciation enrichment data."""

    @abstractmethod
    def upsert(self, pronunciation: CandidatePronunciation) -> None: ...
