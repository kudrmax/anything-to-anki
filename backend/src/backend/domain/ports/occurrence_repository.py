from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.occurrence import Occurrence, OccurrenceKey
    from backend.domain.services.rebuild_plan import RebuildPlan, SectionChange
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.occurrence_row import OccurrenceRow
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin_kind import ShownBy
    from backend.domain.value_objects.unsectioned_phrase import UnsectionedPhrase
    from backend.domain.value_objects.word_row import WordRow


class OccurrenceRepository(ABC):
    """Port for the phrases of words."""

    @abstractmethod
    def by_source(self, source_id: int) -> list[Occurrence]:
        """Every phrase of the source with its results, active binding and active-job marks."""

    @abstractmethod
    def projection(self, source_id: int) -> list[OccurrenceRow]:
        """Every phrase of the source, light."""

    @abstractmethod
    def get(self, occurrence_id: int) -> Occurrence | None: ...

    @abstractmethod
    def of_word(self, candidate_id: int) -> list[Occurrence]:
        """Every phrase of the word with its results, in the order they were made."""

    @abstractmethod
    def decision_phrases(self, candidate_ids: list[int]) -> dict[int, Occurrence]:
        """Word id → the phrase of its decision, with results; undecided words are left out."""

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
        earned_section: CandidateSection,
        polished: Phrase | None = None,
        polish_reverted: bool = False,
        edited_by_user: bool = False,
    ) -> None:
        """The only way to change a phrase's text; rewrites its words from the text it shows.

        When the text the phrase shows changes, its revision goes up: a running job was made
        for the old text and ends without writing, while its queued jobs follow the new text
        (a queued polish still skips a phrase that has a polished text by then).
        `earned_section` is the section of the phrase the card shows after the write; it is
        always stored. `edited_by_user` marks the phrase as cut by the user; the mark is never
        taken off."""

    @abstractmethod
    def holds_revision(self, occurrence_id: int, revision: int) -> bool:
        """True when the phrase still exists at this revision of its text; it then stays so
        until the caller's transaction ends, so a result written meanwhile is for this text."""

    @abstractmethod
    def set_key(self, occurrence_id: int, key: OccurrenceKey | None) -> None:
        """Where the target of the phrase starts in the document."""

    @abstractmethod
    def set_shown(self, ids: list[int], shown_by: ShownBy | None) -> None: ...

    @abstractmethod
    def set_replaces_selection(self, occurrence_id: int, replaces: bool) -> None:
        """Mark a phrase the user put in place of the word's selection card."""

    @abstractmethod
    def reset_results(self, occurrence_id: int) -> None:
        """Drop everything made for the phrase: polish, meaning, media, tts, cloze."""

    @abstractmethod
    def shown_by_word(self, source_id: int) -> dict[int, list[Occurrence]]:
        """Shown phrases of the source with their results, by word id."""

    @abstractmethod
    def word_rows(self, source_id: int) -> list[WordRow]:
        """Every word of the source, light."""

    @abstractmethod
    def apply_plan(self, plan: RebuildPlan) -> list[int]:
        """Write a rebuild plan in the caller's transaction: words, phrases, their words
        and the selection marks. Returns the ids of the inserted phrases, in the order of
        `plan.occ_to_insert`."""

    @abstractmethod
    def unsectioned(self) -> list[UnsectionedPhrase]:
        """Every phrase with no earned section, read without the section the entity needs."""

    @abstractmethod
    def set_earned_sections(self, changes: Sequence[SectionChange]) -> None: ...
