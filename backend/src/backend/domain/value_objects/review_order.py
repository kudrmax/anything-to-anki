"""The order of an open review, held from its opening, and the rows of its visible list.

A book's review holds a hundred thousand cards for as long as it is open, so both are kept in
flat arrays, with no object per card: a held review weighs a few megabytes and adds nothing
for the garbage collector to walk. A card or a row becomes an object only when it is read,
and a card is found by its phrase id without a scan.
"""
from __future__ import annotations

from array import array
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator

_IDS = "q"
_INDICES = "I"
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
    into sections; text order has none. It never changes once made."""

    def __init__(self, cards: Iterable[HeldCard], *, sectioned: bool) -> None:
        phrase_ids, word_ids, codes = array(_IDS), array(_IDS), bytearray()
        for card in cards:
            phrase_ids.append(card.phrase_id)
            word_ids.append(card.word_id)
            codes.append(_SECTION_CODE[card.section])
        self._phrase_ids = phrase_ids
        self._word_ids = word_ids
        self._sections = bytes(codes)
        self._in_section: dict[CandidateSection, array[int]] = {}
        self._rank = array(_INDICES)
        for index, code in enumerate(codes):
            held = self._in_section.setdefault(_SECTIONS[code], array(_INDICES))
            self._rank.append(len(held))
            held.append(index)
        by_id = sorted(range(len(phrase_ids)), key=phrase_ids.__getitem__)
        self._sorted_ids = array(_IDS, (phrase_ids[i] for i in by_id))
        self._sorted_at = array(_INDICES, by_id)
        self.held_sections = frozenset(self._in_section)
        self.sectioned = sectioned

    @property
    def phrase_ids(self) -> Sequence[int]:
        return memoryview(self._phrase_ids).toreadonly()

    @property
    def word_ids(self) -> Sequence[int]:
        return memoryview(self._word_ids).toreadonly()

    @property
    def cards(self) -> _HeldCards:
        return _HeldCards(self)

    def at(self, index: int) -> HeldCard:
        return HeldCard(
            self._phrase_ids[index], self._word_ids[index], _SECTIONS[self._sections[index]],
        )

    def phrase_id_at(self, index: int) -> int:
        return self._phrase_ids[index]

    def section_at(self, index: int) -> CandidateSection:
        return _SECTIONS[self._sections[index]]

    def in_section(self, section: CandidateSection) -> Sequence[int]:
        """The indices of the section's cards, in order."""
        held = self._in_section.get(section)
        return memoryview(held).toreadonly() if held is not None else ()

    def rank_at(self, index: int) -> int:
        """How many cards of its section stand above the card."""
        return self._rank[index]

    def card(self, phrase_id: int) -> HeldCard | None:
        index = self.index_of(phrase_id)
        return None if index is None else self.at(index)

    def index_of(self, phrase_id: int) -> int | None:
        """Where the card stands in the order, None when the review does not hold it."""
        found = bisect_left(self._sorted_ids, phrase_id)
        if found < len(self._sorted_ids) and self._sorted_ids[found] == phrase_id:
            return self._sorted_at[found]
        return None

    def sections_of(self, phrase_ids: Collection[int]) -> dict[int, CandidateSection]:
        """Phrase id → its held section, for the ones of these the review holds."""
        found: dict[int, CandidateSection] = {}
        for phrase_id in phrase_ids:
            index = self.index_of(phrase_id)
            if index is not None:
                found[phrase_id] = self.section_at(index)
        return found

    def __len__(self) -> int:
        return len(self._phrase_ids)


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


type CardRun = tuple[CandidateSection | None, Sequence[int]]


class ReviewLayout:
    """The rows of the visible list, top to bottom. `total_cards`: its card rows.

    Kept as runs of card rows, each the order's indices of the cards of one section (or of
    the whole order, section None, in text order), and the section rows with how many card
    rows stand above each: a layout costs nothing per card."""

    def __init__(
        self,
        order: ReviewOrder,
        runs: Sequence[CardRun],
        section_rows: Sequence[tuple[int, SectionRow]],
    ) -> None:
        self._order = order
        self._runs = tuple(indices for _section, indices in runs)
        starts: list[int] = []
        self._start_of: dict[CandidateSection | None, int] = {}
        total = 0
        for section, indices in runs:
            starts.append(total)
            self._start_of[section] = total
            total += len(indices)
        self._starts = tuple(starts)
        self._sections = tuple(section_rows)
        self.total_cards = total

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
        run = next(n for n in range(len(self._runs) - 1, -1, -1) if self._starts[n] <= card)
        order_index = self._runs[run][card - self._starts[run]]
        return CardRow(self._order.phrase_id_at(order_index), card + 1)

    def index_of(self, phrase_id: int) -> int | None:
        """The row of the card, None when it does not show."""
        order_index = self._order.index_of(phrase_id)
        if order_index is None:
            return None
        if None in self._start_of:
            card = self._start_of[None] + order_index
        else:
            start = self._start_of.get(self._order.section_at(order_index))
            if start is None:
                return None
            card = start + self._order.rank_at(order_index)
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
