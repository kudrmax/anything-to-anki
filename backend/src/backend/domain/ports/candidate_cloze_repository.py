from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_cloze import CandidateCloze


class CandidateClozeRepository(ABC):
    """Port for persisting the user's cloze markup of a candidate."""

    # ── by phrase ──────────────────────────────────────────────────────

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateCloze | None: ...

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, cloze: CandidateCloze) -> None: ...

    @abstractmethod
    def delete_by_phrase_id(self, phrase_id: int) -> None: ...

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateCloze | None: ...

    @abstractmethod
    def upsert(self, cloze: CandidateCloze) -> None: ...

    @abstractmethod
    def delete_by_candidate_id(self, candidate_id: int) -> None: ...
