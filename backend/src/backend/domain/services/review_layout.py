"""The visible list of an open review: which sections fold, the rows of the list and the
card the review opens on.

Ready never folds and has no row. The sections under it fold until the user opens them;
the section of the current card opens by itself and stays open while it holds it. Text order
has no sections: every card shows, in held order.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.candidate_sections import SECTION_ORDER
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.review_order import ReviewLayout, SectionRow

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.review_order import CardRun, ReviewOrder

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
