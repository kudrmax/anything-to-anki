"""The visible list of an open review: which sections fold, the rows of the list and the
card the review opens on.

Ready never folds and has no row. The sections under it fold until the user opens them;
the section of the current card opens by itself and stays open while it holds it. Text order
has no sections: every card shows, in held order.
"""
from __future__ import annotations

from array import array
from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import SECTION_ORDER
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.review_order import ReviewLayout, SectionRow

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.review_order import ReviewOrder

FOLDED_BY_DEFAULT: frozenset[CandidateSection] = frozenset({
    CandidateSection.EXTRA,
    CandidateSection.PROBABLY_KNOWN,
    CandidateSection.REVIEWED,
})
_FOLDING = tuple(sorted(FOLDED_BY_DEFAULT, key=SECTION_ORDER.__getitem__))


def unfolded(
    order: ReviewOrder, opened: frozenset[CandidateSection], current: int | None,
) -> frozenset[CandidateSection]:
    """The sections that show their cards: those the user opened and the current card's."""
    if not order.sectioned or current is None:
        return opened
    held = order.card(current)
    return opened if held is None else opened | {held.section}


def layout(
    order: ReviewOrder, opened: frozenset[CandidateSection], current: int | None,
) -> ReviewLayout:
    """The rows of the visible list: the Ready cards, then the row of each folding section
    that holds a card, with its cards under it when it is open."""
    if not order.sectioned:
        return ReviewLayout(order.phrase_ids, ())
    shown = unfolded(order, opened, current)
    of_section: dict[CandidateSection, array[int]] = {}
    for index, phrase_id in enumerate(order.phrase_ids):
        section = order.section_at(index)
        if section not in of_section:
            of_section[section] = array(order.phrase_ids.typecode)
        of_section[section].append(phrase_id)
    cards = of_section.get(CandidateSection.READY, array(order.phrase_ids.typecode))
    section_rows: list[tuple[int, SectionRow]] = []
    for section in _FOLDING:
        held = of_section.get(section)
        if not held:
            continue
        is_open = section in shown
        section_rows.append((len(cards), SectionRow(section, len(held), is_open)))
        if is_open:
            cards.extend(held)
    return ReviewLayout(cards, section_rows)


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
    return order.phrase_ids[0] if len(order) else None
