from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage


class CandidateMeaningImageRepository(ABC):
    """Port for persisting the meaning image of a candidate."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaningImage | None: ...

    @abstractmethod
    def upsert(self, image: CandidateMeaningImage) -> None: ...

    @abstractmethod
    def delete_by_candidate_id(self, candidate_id: int) -> None: ...
