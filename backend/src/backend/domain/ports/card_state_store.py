from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.card_state_rows import (
        CardStateRow,
        CardStates,
        PhraseWordKind,
        PhraseWordRow,
        StoredCardState,
        StoredCardStates,
        WordStateRow,
    )
    from backend.domain.value_objects.phrase_newness import PhraseNewness
    from backend.domain.value_objects.user_knowledge import Newness


class CardStateStore(ABC):
    """Port for the stored projection of card state. Only the projector writes it; the
    rules never read it. Lemmas are compared as stored, in lower case."""

    @abstractmethod
    def next_revision(self) -> int:
        """Moves the projection's revision one up and returns the new one."""

    @abstractmethod
    def replace_all(self, states: CardStates, revision: int) -> None:
        """Every row of the projection becomes `states`, each written at `revision`. A card
        stored before and missing from `states` stays as a removed row at `revision`."""

    @abstractmethod
    def read_all(self) -> StoredCardStates:
        """Every stored row, removed cards included."""

    @abstractmethod
    def cards(self, phrase_ids: Collection[int]) -> dict[int, StoredCardState]:
        """The stored cards of these phrases by phrase id, removed ones included."""

    @abstractmethod
    def live_cards_of_words(self, word_ids: Collection[int]) -> list[StoredCardState]:
        """The stored cards of these words that are not removed."""

    @abstractmethod
    def live_cards_of_source(self, source_id: int) -> list[StoredCardState]:
        """The stored cards of the source that are not removed."""

    @abstractmethod
    def words(self, word_ids: Collection[int]) -> dict[int, WordStateRow]:
        """The stored words with these ids, by id."""

    @abstractmethod
    def words_of_source(
        self, source_id: int, lemmas: Collection[str] | None = None,
    ) -> list[WordStateRow]:
        """The stored words of the source; only those of `lemmas` when given."""

    @abstractmethod
    def phrase_newness(self, phrase_ids: Collection[int]) -> dict[int, PhraseNewness]:
        """The newness of the stored other words of these phrases, by phrase id; a phrase
        without one is left out."""

    @abstractmethod
    def phrase_word_kinds(self, lemmas: Collection[str]) -> set[PhraseWordKind]:
        """The kinds of the stored other words of these lemmas."""

    @abstractmethod
    def set_newness(self, kind: PhraseWordKind, newness: Newness) -> set[int]:
        """Every stored other word of the kind gets `newness`; returns the phrases where one
        had another."""

    @abstractmethod
    def write_cards(self, rows: Collection[CardStateRow], revision: int) -> None:
        """Each card stored as `rows` says, at `revision`, removed or not before."""

    @abstractmethod
    def write_sections(self, rows: Collection[CardStateRow], revision: int) -> None:
        """Stored live cards whose only change is their sections and new-word counts take
        those of `rows`, at `revision`."""

    @abstractmethod
    def remove_cards(self, phrase_ids: Collection[int], revision: int) -> None:
        """The stored cards of these phrases stay as removed rows at `revision`; their other
        words go."""

    @abstractmethod
    def replace_phrase_words(
        self, phrase_ids: Collection[int], rows: Collection[PhraseWordRow],
    ) -> None:
        """The stored other words of these phrases become `rows`."""

    @abstractmethod
    def write_words(self, rows: Collection[WordStateRow]) -> None:
        """Each word stored as `rows` says."""

    @abstractmethod
    def delete_words(self, word_ids: Collection[int]) -> None:
        """The stored words with these ids go."""

    @abstractmethod
    def touch_cards(
        self, phrase_ids: Collection[int], word_ids: Collection[int], revision: int,
    ) -> None:
        """The cards of these phrases and of these words that are not removed move to
        `revision`, their values as they are."""
