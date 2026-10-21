"""The order of an open review, held from its opening, and the rows of its visible list.

A book's review holds a hundred thousand cards for as long as it is open, so both are kept in
flat arrays, with no object per card: a held review weighs a few megabytes and adds nothing
for the garbage collector to walk. A card or a row becomes an object only when it is read.
"""
from __future__ import annotations

from array import array
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator

_IDS = "q"
_SECTIONS: tuple[CandidateSection, ...] = tuple(CandidateSection)
_SECTION_CODE: dict[CandidateSection, int] = {s: i for i, s in enumerate(_SECTIONS)}


@dataclass(frozen=True, slots=True)
class HeldCard:
    """A card of an open review: where it stood when the review opened."""

    phrase_id: int
    word_id: int
    section: CandidateSection


class ReviewOrder:
    """The cards of an open review in the order it opened with. `sectioned`: the list is cut
    into sections; text order has none."""

    def __init__(self, cards: Iterable[HeldCard], *, sectioned: bool) -> None:
        self.phrase_ids = array(_IDS)
        self.word_ids = array(_IDS)
        codes = bytearray()
        for card in cards:
            self.phrase_ids.append(card.phrase_id)
            self.word_ids.append(card.word_id)
            codes.append(_SECTION_CODE[card.section])
        self._sections = bytes(codes)
        self.sectioned = sectioned

    @property
    def cards(self) -> _HeldCards:
        return _HeldCards(self)

    def at(self, index: int) -> HeldCard:
        return HeldCard(
            self.phrase_ids[index], self.word_ids[index], _SECTIONS[self._sections[index]],
        )

    def section_at(self, index: int) -> CandidateSection:
        return _SECTIONS[self._sections[index]]

    def card(self, phrase_id: int) -> HeldCard | None:
        index = self.index_of(phrase_id)
        return None if index is None else self.at(index)

    def index_of(self, phrase_id: int) -> int | None:
        try:
            return self.phrase_ids.index(phrase_id)
        except ValueError:
            return None

    def sections_of(self, phrase_ids: Collection[int]) -> dict[int, CandidateSection]:
        """Phrase id → its held section, for the ones of these the review holds."""
        wanted = set(phrase_ids)
        return {
            phrase_id: _SECTIONS[self._sections[index]]
            for index, phrase_id in enumerate(self.phrase_ids) if phrase_id in wanted
        }

    def __len__(self) -> int:
        return len(self.phrase_ids)


class _HeldCards(Sequence[HeldCard]):
    """The held cards in order, each made when read."""

    def __init__(self, order: ReviewOrder) -> None:
        self._order = order

    def __len__(self) -> int:
        return len(self._order)

    @overload
    def __getitem__(self, index: int) -> HeldCard: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[HeldCard]: ...

    def __getitem__(self, index: int | slice) -> HeldCard | Sequence[HeldCard]:
        if isinstance(index, slice):
            return [self._order.at(i) for i in range(len(self))[index]]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        return self._order.at(index)

    def __iter__(self) -> Iterator[HeldCard]:
        return (self._order.at(i) for i in range(len(self)))


@dataclass(frozen=True, slots=True)
class CardRow:
    """A card of the visible list; `position` counts card rows from 1."""

    phrase_id: int
    position: int


@dataclass(frozen=True, slots=True)
class SectionRow:
    """The row of a section that folds: how many cards it holds and whether they show."""

    section: CandidateSection
    count: int
    open: bool


type LayoutRow = CardRow | SectionRow


class ReviewLayout:
    """The rows of the visible list, top to bottom. `total_cards`: its card rows.

    Kept as the phrase ids of the card rows and the section rows with how many card rows
    stand above each."""

    def __init__(
        self, card_rows: array[int], section_rows: Sequence[tuple[int, SectionRow]],
    ) -> None:
        self._cards = card_rows
        self._sections = tuple(section_rows)
        self.total_cards = len(card_rows)

    @property
    def rows(self) -> _LayoutRows:
        return _LayoutRows(self)

    def __len__(self) -> int:
        return self.total_cards + len(self._sections)

    def row(self, index: int) -> LayoutRow:
        if not 0 <= index < len(self):
            raise IndexError(index)
        above = 0
        for number, (cards_above, section_row) in enumerate(self._sections):
            at = cards_above + number
            if at == index:
                return section_row
            if at < index:
                above += 1
        card = index - above
        return CardRow(self._cards[card], card + 1)

    def index_of(self, phrase_id: int) -> int | None:
        """The row of the card, None when it does not show."""
        try:
            card = self._cards.index(phrase_id)
        except ValueError:
            return None
        return self._row_of_card(card)

    def section_indices(self) -> list[int]:
        """The rows of the sections."""
        return [cards_above + number for number, (cards_above, _row) in enumerate(self._sections)]

    def indices_of(self, phrase_ids: Collection[int]) -> list[int]:
        """The rows of those of these cards that show, top to bottom."""
        wanted = set(phrase_ids)
        return [
            self._row_of_card(card)
            for card, phrase_id in enumerate(self._cards) if phrase_id in wanted
        ]

    def _row_of_card(self, card: int) -> int:
        return card + sum(1 for cards_above, _row in self._sections if cards_above <= card)


class _LayoutRows(Sequence[LayoutRow]):
    """The rows of a layout in order, each made when read."""

    def __init__(self, layout: ReviewLayout) -> None:
        self._layout = layout

    def __len__(self) -> int:
        return len(self._layout)

    @overload
    def __getitem__(self, index: int) -> LayoutRow: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[LayoutRow]: ...

    def __getitem__(self, index: int | slice) -> LayoutRow | Sequence[LayoutRow]:
        if isinstance(index, slice):
            return [self._layout.row(i) for i in range(len(self))[index]]
        if index < 0:
            index += len(self)
        return self._layout.row(index)

    def __iter__(self) -> Iterator[LayoutRow]:
        return (self._layout.row(i) for i in range(len(self)))
