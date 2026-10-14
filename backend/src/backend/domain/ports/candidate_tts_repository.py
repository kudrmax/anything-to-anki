from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_tts import CandidateTTS


class CandidateTTSRepository(ABC):
    """Port for persisting TTS audio enrichment data."""

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateTTS | None: ...

    @abstractmethod
    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateTTS]:
        """Keyed by phrase id; phrases without a row are left out."""

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, tts: CandidateTTS) -> None: ...

    @abstractmethod
    def delete_by_phrase_id(self, phrase_id: int) -> None: ...
