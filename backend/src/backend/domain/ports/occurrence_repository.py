from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.occurrence_row import OccurrenceRow
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import DecisionKind, ShownBy


class OccurrenceRepository(ABC):
    """Port for the phrases of words."""

    @abstractmethod
    def by_source(self, source_id: int) -> list[Occurrence]:
        """Every phrase of the source with its results, export and active-job marks."""

    @abstractmethod
    def projection(self, source_id: int) -> list[OccurrenceRow]:
        """Every phrase of the source, light."""

    @abstractmethod
    def get(self, occurrence_id: int) -> Occurrence | None: ...

    @abstractmethod
    def add(self, occurrence: Occurrence) -> Occurrence:
        """Store a new phrase; its words are taken from the text it shows."""

    @abstractmethod
    def write_text(
        self,
        occurrence_id: int,
        phrase: Phrase,
        position: DocumentPosition | None,
        *,
        polished: Phrase | None = None,
        polish_reverted: bool = False,
        bump_revision: bool = False,
    ) -> None:
        """The only way to change a phrase's text; rewrites its words from the text it shows."""

    @abstractmethod
    def set_shown(self, ids: list[int], shown_by: ShownBy | None) -> None: ...

    @abstractmethod
    def set_skipped(self, occurrence_id: int, skipped: bool) -> None: ...

    @abstractmethod
    def set_decision(
        self, candidate_id: int, occurrence_id: int | None, kind: DecisionKind | None,
    ) -> None:
        """The phrase of the word's decision, or none; any other phrase loses the mark."""

    @abstractmethod
    def reset_results(self, occurrence_id: int) -> None:
        """Drop everything made for the phrase: polish, meaning, media, tts, cloze."""

    @abstractmethod
    def shown_by_word(self, source_id: int) -> dict[int, list[Occurrence]]:
        """Shown phrases of the source with their results, by word id."""
