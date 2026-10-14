from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_tts import CandidateTTS


class CandidateTTSRepository(ABC):
    """Port for persisting TTS audio enrichment data."""

    # ── by phrase ──────────────────────────────────────────────────────

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateTTS | None: ...

    @abstractmethod
    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateTTS]:
        """Keyed by phrase id; phrases without a row are left out."""

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, tts: CandidateTTS) -> None: ...

    @abstractmethod
    def delete_by_phrase_id(self, phrase_id: int) -> None: ...

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateTTS | None: ...

    @abstractmethod
    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidateTTS]: ...

    @abstractmethod
    def upsert(self, tts: CandidateTTS) -> None: ...

    @abstractmethod
    def delete_by_candidate_id(self, candidate_id: int) -> None: ...

    @abstractmethod
    def get_eligible_candidate_ids(self, source_id: int) -> list[int]:
        """Return ids of candidates that have status PENDING or LEARN
        and do NOT have an existing CandidateTTS row.
        Used by enqueue TTS generation use case."""
        ...
