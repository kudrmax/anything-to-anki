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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, overload

from backend.domain.value_objects.candidate_section import CandidateSection

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping

    from backend.domain.services.candidate_sorting import OrderKey

_IDS = "q"
_INDICES = "I"
_SECTIONS: tuple[CandidateSection, ...] = tuple(CandidateSection)
_SECTION_CODE: dict[CandidateSection, int] = {s: i for i, s in enumerate(_SECTIONS)}


@dataclass(frozen=True, slots=True)
class HeldCard:
    """A card of an open review: where it stood when the review opened. `key`: the sort key
    it was held by, which new cards are placed against; an order holds one for every card
    or for none."""

    phrase_id: int
    word_id: int
    section: CandidateSection
    key: OrderKey | None = field(default=None, compare=False)


# Any: a column holds ints or floats, as its typecode says.
type _Column = array[Any]
_INT_CODE = "i"
_FLOAT_CODE = "d"
_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1


def _flat(key: OrderKey) -> tuple[float | int, ...]:
    part, best, word_id, own, phrase_id = key
    return (part, *best, word_id, *own, phrase_id)


def _fits(column: _Column, value: float | int) -> bool:
    if column.typecode == _FLOAT_CODE:
        return True
    return not isinstance(value, float) and _INT_MIN <= value <= _INT_MAX


class _KeyColumns:
    """The held keys of an order, one flat array per part of a key: no object per card. A
    column holds 4-byte ints until a value needs a float."""

    def __init__(self, columns: list[_Column], own_length: int) -> None:
        self.columns = columns
        self._own = own_length

    @classmethod
    def empty_like(cls, other: _KeyColumns) -> _KeyColumns:
        return cls([array(c.typecode) for c in other.columns], other._own)  # noqa: SLF001

    @classmethod
    def of(cls, first: OrderKey) -> _KeyColumns:
        own = len(first[3])
        return cls([array(_INT_CODE) for _ in _flat(first)], own)

    @classmethod
    def of_all(cls, keys: Sequence[OrderKey]) -> _KeyColumns:
        """The keys, a column at a time: an opening holds a whole book's."""
        columns: list[_Column] = []
        for values in zip(*(_flat(key) for key in keys), strict=True):
            ints = not any(isinstance(v, float) for v in values) and (
                min(values) >= _INT_MIN and max(values) <= _INT_MAX
            )
            columns.append(array(_INT_CODE if ints else _FLOAT_CODE, values))
        return cls(columns, len(keys[0][3]))

    def append(self, key: OrderKey) -> None:
        self.append_flat(_flat(key))

    def append_flat(self, values: Sequence[float | int]) -> None:
        for at, value in enumerate(values):
            column = self.columns[at]
            if not _fits(column, value):
                column = self.columns[at] = array(_FLOAT_CODE, column)
            column.append(value)

    def extend(self, other: _KeyColumns, start: int, stop: int) -> None:
        """The keys of `other` from `start` to `stop`, appended."""
        for at, column in enumerate(other.columns):
            mine = self.columns[at]
            if mine.typecode == column.typecode:
                mine.extend(column[start:stop])
            elif mine.typecode == _FLOAT_CODE:
                mine.extend(float(value) for value in column[start:stop])
            else:
                self.columns[at] = array(_FLOAT_CODE, mine)
                self.columns[at].extend(column[start:stop])

    def flat(self, index: int) -> tuple[float | int, ...]:
        return tuple(column[index] for column in self.columns)

    def key(self, index: int) -> OrderKey:
        values = self.flat(index)
        best = len(values) - self._own - 3
        return (
            int(values[0]), tuple(values[1:1 + best]), int(values[1 + best]),
            tuple(values[2 + best:-1]), int(values[-1]),
        )

    def nbytes(self) -> int:
        return sum(column.itemsize * len(column) for column in self.columns)


class ReviewOrder:
    """The cards of an open review in the order it opened with. `sectioned`: the list is cut
    into sections; text order has none. It never changes once made."""

    def __init__(self, cards: Iterable[HeldCard], *, sectioned: bool) -> None:
        phrase_ids, word_ids, codes = array(_IDS), array(_IDS), bytearray()
        held_keys: list[OrderKey] = []
        for card in cards:
            phrase_ids.append(card.phrase_id)
            word_ids.append(card.word_id)
            codes.append(_SECTION_CODE[card.section])
            if card.key is not None:
                held_keys.append(card.key)
        if held_keys and len(held_keys) != len(phrase_ids):
            msg = "an order holds a key for every card or for none"
            raise ValueError(msg)
        keys = _KeyColumns.of_all(held_keys) if held_keys else None
        self._hold(phrase_ids, word_ids, bytes(codes), keys, sectioned=sectioned)

    @classmethod
    def _of_columns(
        cls,
        phrase_ids: array[int],
        word_ids: array[int],
        codes: bytes,
        keys: _KeyColumns | None,
        *,
        sectioned: bool,
    ) -> ReviewOrder:
        order = cls.__new__(cls)
        order._hold(phrase_ids, word_ids, codes, keys, sectioned=sectioned)
        return order

    def _hold(
        self,
        phrase_ids: array[int],
        word_ids: array[int],
        codes: bytes,
        keys: _KeyColumns | None,
        *,
        sectioned: bool,
    ) -> None:
        self._phrase_ids = phrase_ids
        self._word_ids = word_ids
        self._sections = codes
        self._keys = keys
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
            None if self._keys is None else self._keys.key(index),
        )

    @property
    def has_keys(self) -> bool:
        return self._keys is not None

    def key_at(self, index: int) -> OrderKey:
        """The sort key the card at `index` is held by. The held cards stand in the order of
        these keys, every one below the next."""
        if self._keys is None:
            msg = "this order holds no keys"
            raise ValueError(msg)
        return self._keys.key(index)

    def keys_nbytes(self) -> int:
        """What the held keys weigh."""
        return 0 if self._keys is None else self._keys.nbytes()

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

    def spliced(
        self,
        *,
        dropped: Collection[int] = (),
        replaced: Mapping[int, HeldCard] | None = None,
        following: Mapping[int | None, Sequence[HeldCard]] | None = None,
    ) -> ReviewOrder:
        """A new order from this one: the `dropped` cards left out, each card of `replaced`
        in the place of the one it names, and the cards of `following` right after the one
        each list names (at the top for None). Built column by column, with no object per
        held card."""
        replaced = replaced or {}
        following = following or {}
        phrase_ids, word_ids, codes = array(_IDS), array(_IDS), bytearray()
        # An empty order takes the keys of the first cards put into it.
        keyed = [None if self._keys is None else _KeyColumns.empty_like(self._keys)]

        def put(card: HeldCard, held_at: int | None = None) -> None:
            """A card of the new order; one put in place of the card at `held_at` takes that
            card's key, so the order stays in key order."""
            phrase_ids.append(card.phrase_id)
            word_ids.append(card.word_id)
            codes.append(_SECTION_CODE[card.section])
            keys = keyed[0]
            if keys is None and not len(self) and card.key is not None and len(phrase_ids) == 1:
                keys = keyed[0] = _KeyColumns.of(card.key)
            if keys is None:
                return
            if held_at is not None:
                assert self._keys is not None
                keys.append_flat(self._keys.flat(held_at))
            elif card.key is not None:
                keys.append(card.key)
            else:
                msg = "a card put into an order of keys needs its key"
                raise ValueError(msg)

        for card in following.get(None, ()):
            put(card)
        marked = (
            {*dropped, *replaced, *(k for k in following if k is not None)}
        )
        start = 0
        for index in sorted(i for p in marked if (i := self.index_of(p)) is not None):
            phrase_ids.extend(self._phrase_ids[start:index])
            word_ids.extend(self._word_ids[start:index])
            codes.extend(self._sections[start:index])
            if keyed[0] is not None and self._keys is not None:
                keyed[0].extend(self._keys, start, index)
            start = index + 1
            phrase_id = self._phrase_ids[index]
            if phrase_id in replaced:
                put(replaced[phrase_id], held_at=index)
            elif phrase_id not in dropped:
                put(self.at(index), held_at=index)
            for card in following.get(phrase_id, ()):
                put(card)
        phrase_ids.extend(self._phrase_ids[start:])
        word_ids.extend(self._word_ids[start:])
        codes.extend(self._sections[start:])
        if keyed[0] is not None and self._keys is not None:
            keyed[0].extend(self._keys, start, len(self._phrase_ids))
        return ReviewOrder._of_columns(
            phrase_ids, word_ids, bytes(codes), keyed[0], sectioned=self.sectioned,
        )


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
