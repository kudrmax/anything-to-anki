"""The visible list of an open review: which sections fold, the rows of the list, the card
the review opens on, and how the held order and the focus follow what changes while it is
open.

Ready never folds and has no row. The sections under it fold until the user opens them;
the section of the current card opens by itself and stays open while it holds it. Text order
has no sections: every card shows, in held order.
"""
from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import SECTION_ORDER
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.review_order import CardRow, ReviewLayout, SectionRow

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from backend.domain.services.candidate_sorting import OrderKey
    from backend.domain.value_objects.review_order import CardRun, HeldCard, ReviewOrder

FOLDED_BY_DEFAULT: frozenset[CandidateSection] = frozenset({
    CandidateSection.EXTRA,
    CandidateSection.PROBABLY_KNOWN,
    CandidateSection.REVIEWED,
})
_FOLDING = tuple(sorted(FOLDED_BY_DEFAULT, key=SECTION_ORDER.__getitem__))


def unfolded(
    order: ReviewOrder, opened: frozenset[CandidateSection], current: int | None,
) -> frozenset[CandidateSection]:
    """The folding sections that hold cards and show them: those the user opened and the
    current card's. Two reviews with the same unfolded sections show the same list."""
    if not order.sectioned:
        return frozenset()
    shown = set(opened)
    if current is not None:
        held = order.card(current)
        if held is not None:
            shown.add(held.section)
    return frozenset(shown & FOLDED_BY_DEFAULT & order.held_sections)


def layout(
    order: ReviewOrder, opened: frozenset[CandidateSection], current: int | None,
) -> ReviewLayout:
    """The rows of the visible list: the Ready cards, then the row of each folding section
    that holds a card, with its cards under it when it is open."""
    if not order.sectioned:
        return ReviewLayout(order, ((None, range(len(order))),), ())
    shown = unfolded(order, opened, current)
    runs: list[CardRun] = [(CandidateSection.READY, order.in_section(CandidateSection.READY))]
    cards = len(runs[0][1])
    section_rows: list[tuple[int, SectionRow]] = []
    for section in _FOLDING:
        held = order.in_section(section)
        if not held:
            continue
        is_open = section in shown
        section_rows.append((cards, SectionRow(section, len(held), is_open)))
        if is_open:
            runs.append((section, held))
            cards += len(held)
    return ReviewLayout(order, runs, section_rows)


def initial_focus(
    order: ReviewOrder, is_done: Mapping[int, bool], requested: int | None,
) -> int | None:
    """The card the review opens on: the one asked for if the review holds it, else the
    first one not done, else the first one."""
    if requested is not None and order.card(requested) is not None:
        return requested
    pending = next((p for p in order.phrase_ids if not is_done[p]), None)
    if pending is not None:
        return pending
    return order.phrase_id_at(0) if len(order) else None


def focus_after_press(
    order: ReviewOrder, pressed: int, was_done: bool, is_done: Mapping[int, bool],
) -> int | None:
    """Where the focus goes after a press: nowhere unless the pressed card became done.
    Then the first card after it in held order that is not done, within its held section
    when the list has sections; from the top when none is left after it. The pressed card
    stays where it stood, so it is never the answer."""
    index = order.index_of(pressed)
    if was_done or index is None or not is_done[pressed]:
        return None
    if order.sectioned:
        run: Sequence[int] = order.in_section(order.section_at(index))
        start = order.rank_at(index)
    else:
        run, start = range(len(order)), index
    for at in chain(range(start, len(run)), range(start)):
        phrase_id = order.phrase_id_at(run[at])
        if phrase_id != pressed and not is_done[phrase_id]:
            return phrase_id
    return None


def place_new(
    order: ReviewOrder, fresh: Sequence[HeldCard], new_ids: Collection[int],
) -> ReviewOrder:
    """The new cards placed into the held order: each right after the nearest card before
    it in `fresh` that the order already holds, before every held card when none is. A run
    of new cards keeps its fresh order; each new card takes its fresh section, and the held
    cards keep their place and section."""
    following: dict[int | None, list[HeldCard]] = {}
    anchor: int | None = None
    for card in fresh:
        if order.index_of(card.phrase_id) is not None:
            anchor = card.phrase_id
        elif card.phrase_id in new_ids:
            following.setdefault(anchor, []).append(card)
    if not following:
        return order
    return order.spliced(following=following)


def place_by_key(order: ReviewOrder, new: Sequence[HeldCard]) -> ReviewOrder:
    """The new cards placed by their keys against the keys the held cards were held by: each
    right after the last held card below it, as an order opened on the held cards and the
    new ones would stand. A held card keeps the key of the opening however it changed since,
    so the held cards stay in key order and a binary search finds the place; placing keeps
    that order. Cards placed after the same held card keep their key order."""
    if not new:
        return order
    following: dict[int | None, list[HeldCard]] = {}
    for card in sorted(new, key=_key_of):
        key = _key_of(card)
        low, high = 0, len(order)
        while low < high:
            middle = (low + high) // 2
            if order.key_at(middle) < key:
                low = middle + 1
            else:
                high = middle
        anchor = order.phrase_id_at(low - 1) if low > 0 else None
        following.setdefault(anchor, []).append(card)
    return order.spliced(following=following)


def _key_of(card: HeldCard) -> OrderKey:
    if card.key is None:
        msg = "a card placed by key needs its key"
        raise ValueError(msg)
    return card.key


def replace_card(order: ReviewOrder, old_id: int, new: HeldCard) -> ReviewOrder:
    """The new card in the place of the old one, with its own section."""
    return order.spliced(replaced={old_id: new})


def remove_cards(order: ReviewOrder, phrase_ids: Collection[int]) -> ReviewOrder:
    """The order without these cards."""
    if not any(order.index_of(phrase_id) is not None for phrase_id in phrase_ids):
        return order
    return order.spliced(dropped=frozenset(phrase_ids))


def focus_after_removal(
    before: ReviewLayout, current: int, removed: Collection[int],
) -> int | None:
    """Where the focus goes when the current card is gone: the next card row under it in
    the list as it stood, that is not gone too; else the nearest one above it."""
    index = before.index_of(current)
    if index is None:
        return None
    for at in chain(range(index + 1, len(before)), range(index - 1, -1, -1)):
        row = before.row(at)
        if isinstance(row, CardRow) and row.phrase_id not in removed:
            return row.phrase_id
    return None
