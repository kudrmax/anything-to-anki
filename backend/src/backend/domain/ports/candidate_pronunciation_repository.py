from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation


class CandidatePronunciationRepository(ABC):
    """Port for persisting pronunciation enrichment data."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidatePronunciation | None: ...

    @abstractmethod
    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidatePronunciation]: ...

    @abstractmethod
    def upsert(self, pronunciation: CandidatePronunciation) -> None: ...

    @abstractmethod
    def get_eligible_candidate_ids(self, source_id: int) -> list[int]: ...
