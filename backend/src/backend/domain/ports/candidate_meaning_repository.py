from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning


class CandidateMeaningRepository(ABC):
    """Port for the meaning enrichment of a candidate.

    1:1 with candidates. `None` from get methods means no row exists for this
    candidate (i.e., generation has never been attempted).
    """

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaning | None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMeaning]:
        """Return a mapping {candidate_id: CandidateMeaning} for all rows belonging
        to candidates of the given source. Used to bulk-load enrichments when
        listing candidates."""

    @abstractmethod
    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMeaning]:
        """Return a mapping for the explicit list of candidate ids."""

    @abstractmethod
    def upsert(self, meaning: CandidateMeaning) -> None:
        """Insert or update the meaning row for the contained candidate_id."""
