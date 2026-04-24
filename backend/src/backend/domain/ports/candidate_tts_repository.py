from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_tts import CandidateTTS


class CandidateTTSRepository(ABC):
    """Port for persisting TTS audio enrichment data."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateTTS | None: ...

    @abstractmethod
    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidateTTS]: ...

    @abstractmethod
    def upsert(self, tts: CandidateTTS) -> None: ...

    @abstractmethod
    def get_eligible_candidate_ids(self, source_id: int) -> list[int]:
        """Return ids of candidates that have status PENDING or LEARN
        and do NOT have an existing CandidateTTS row.
        Used by enqueue TTS generation use case."""
        ...
