from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze


class CandidateClozeRepository(ABC):
    """Port for persisting the user's cloze markup of a candidate."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateCloze | None: ...

    @abstractmethod
    def upsert(self, cloze: CandidateCloze) -> None: ...

    @abstractmethod
    def delete_by_candidate_id(self, candidate_id: int) -> None: ...
