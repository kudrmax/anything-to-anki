from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning


class CandidateMeaningRepository(ABC):
    """Port for the meanings of phrases. No row: generation was never attempted."""

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateMeaning | None: ...

    @abstractmethod
    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMeaning]:
        """Keyed by phrase id; phrases without a row are left out."""

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, meaning: CandidateMeaning) -> None: ...

    @abstractmethod
    def delete_by_phrase_id(self, phrase_id: int) -> None: ...
