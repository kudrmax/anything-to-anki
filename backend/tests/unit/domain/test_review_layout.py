"""The visible list of an open review, the card it opens on and how the order and the focus
follow changes: the cases of the web app's former `sections.test.ts`, `initialFocus.test.ts`,
`nextFocus.test.ts` and `keptLayout.test.ts`, kept by the backend now."""
from __future__ import annotations

import pytest
from backend.domain.services.review_layout import (
    FOLDED_BY_DEFAULT,
    focus_after_press,
    focus_after_removal,
    initial_focus,
    layout,
    place_new,
    remove_cards,
    replace_card,
    unfolded,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.review_order import (
    CardRow,
    HeldCard,
    LayoutRow,
    ReviewOrder,
    SectionRow,
)

R = CandidateSection.READY
E = CandidateSection.EXTRA
P = CandidateSection.PROBABLY_KNOWN
V = CandidateSection.REVIEWED


def _order(*cards: tuple[int, CandidateSection], sectioned: bool = True) -> ReviewOrder:
    return ReviewOrder(
        tuple(HeldCard(phrase_id, phrase_id * 10, section) for phrase_id, section in cards),
        sectioned=sectioned,
    )


# As the former front fixture: one ready card, two extra, one probably known, one reviewed.
CARDS = _order((1, R), (2, E), (3, E), (4, P), (5, V))


def _rows(
    order: ReviewOrder, opened: set[CandidateSection] | None = None, current: int | None = None,
) -> list[int | str]:
    return [_label(row) for row in layout(order, frozenset(opened or ()), current).rows]


def _label(row: LayoutRow) -> int | str:
    if isinstance(row, CardRow):
        return row.phrase_id
    return f"{row.section.value}{'-' if row.open else '+'}"


def test_every_section_under_ready_folds() -> None:
    assert _rows(CARDS) == [1, "extra+", "probably_known+", "reviewed+"]
    assert frozenset({E, P, V}) == FOLDED_BY_DEFAULT


def test_an_open_section_shows_its_cards_under_its_row() -> None:
    assert _rows(CARDS, {E}) == [1, "extra-", 2, 3, "probably_known+", "reviewed+"]


def test_the_reviewed_cards_are_last_under_their_own_row() -> None:
    assert _rows(CARDS, {V}) == [1, "extra+", "probably_known+", "reviewed-", 5]


def test_a_section_row_counts_its_cards() -> None:
    rows = layout(CARDS, frozenset(), None).rows
    assert [(r.section, r.count, r.open) for r in rows if isinstance(r, SectionRow)] == [
        (E, 2, False), (P, 1, False), (V, 1, False),
    ]


def test_the_current_card_opens_its_folded_section() -> None:
    assert _rows(CARDS, current=4) == [1, "extra+", "probably_known-", 4, "reviewed+"]


def test_the_current_cards_section_stays_open_when_folded() -> None:
    folded = _rows(CARDS, set(), current=2)
    assert folded == [1, "extra-", 2, 3, "probably_known+", "reviewed+"]


def test_a_current_card_the_review_does_not_hold_opens_nothing() -> None:
    assert _rows(CARDS, current=99) == [1, "extra+", "probably_known+", "reviewed+"]


def test_text_order_has_no_section_rows() -> None:
    order = _order((3, E), (1, R), (5, V), (4, P), sectioned=False)
    assert _rows(order) == [3, 1, 5, 4]


def test_positions_count_the_card_rows_only() -> None:
    shown = layout(CARDS, frozenset({E, V}), None)
    positions = [(r.phrase_id, r.position) for r in shown.rows if isinstance(r, CardRow)]
    assert positions == [(1, 1), (2, 2), (3, 3), (5, 4)]
    assert shown.total_cards == 4


def test_an_empty_section_has_no_row() -> None:
    assert _rows(_order((1, R), (5, V))) == [1, "reviewed+"]
    assert _rows(_order()) == []


def test_cards_keep_the_held_order_inside_a_section() -> None:
    order = _order((7, E), (1, R), (2, E), (6, R))
    assert _rows(order, {E}) == [1, 6, "extra-", 7, 2]


def test_the_row_of_a_card() -> None:
    shown = layout(CARDS, frozenset({E}), None)
    assert (shown.index_of(3), shown.index_of(4)) == (3, None)


def test_every_row_is_found_where_the_list_has_it() -> None:
    for opened in (set(), {E}, {P}, {V}, {E, V}, {E, P, V}):
        shown = layout(CARDS, frozenset(opened), None)
        rows = list(shown.rows)
        assert [shown.row(i) for i in range(len(shown))] == rows
        cards = {row.phrase_id: i for i, row in enumerate(rows) if isinstance(row, CardRow)}
        assert {p: shown.index_of(p) for p in cards} == cards
        hidden = {c.phrase_id for c in CARDS.cards} - set(cards)
        assert all(shown.index_of(p) is None for p in (*hidden, 99))


def test_a_row_past_the_list_is_refused() -> None:
    shown = layout(CARDS, frozenset(), None)
    with pytest.raises(IndexError):
        shown.row(len(shown))


def test_the_same_sections_shown_are_the_same_list() -> None:
    """Moving between a Ready card and a card of an open section, or to no card, opens or
    folds nothing: the unfolded sections stay the same."""
    shown = {
        unfolded(CARDS, frozenset({E}), current) for current in (1, 2, 3, None, 99)
    }
    assert shown == {frozenset({E})}
    assert unfolded(CARDS, frozenset({R}), 1) == frozenset()
    assert unfolded(_order((1, R), (2, E)), frozenset({V}), None) == frozenset()
    assert unfolded(_order((1, E), sectioned=False), frozenset({E}), 1) == frozenset()


def test_the_order_cannot_be_changed_through_its_ids() -> None:
    with pytest.raises(TypeError):
        CARDS.phrase_ids[0] = 5  # type: ignore[index]
    with pytest.raises(TypeError):
        CARDS.word_ids[0] = 5  # type: ignore[index]


def test_the_order_reads_back_the_cards_it_holds() -> None:
    held = [HeldCard(4, 40, P), HeldCard(1, 10, R), HeldCard(7, 70, V)]
    order = ReviewOrder(held, sectioned=True)
    assert list(order.cards) == held
    assert (order.cards[-1], order.cards[1:], len(order.cards)) == (held[-1], held[1:], 3)
    assert (order.card(1), order.card(99)) == (held[1], None)
    assert order.sections_of([7, 4, 99]) == {4: P, 7: V}


# --- the card the review opens on ---------------------------------------------------------

def _done(*phrase_ids: int) -> dict[int, bool]:
    return {card.phrase_id: card.phrase_id in phrase_ids for card in CARDS.cards}


def test_it_opens_on_the_card_asked_for_even_a_reviewed_one() -> None:
    order = _order((1, R), (2, V))
    assert initial_focus(order, {1: False, 2: True}, 2) == 2


def test_it_opens_on_the_first_open_card_when_the_link_points_elsewhere() -> None:
    order = _order((2, R), (1, V))
    assert initial_focus(order, {2: False, 1: True}, 99) == 2


def test_it_opens_on_the_first_open_card_without_a_link() -> None:
    order = _order((2, R), (3, R), (1, V))
    assert initial_focus(order, {2: False, 3: False, 1: True}, None) == 2


def test_it_opens_on_the_first_reviewed_card_when_every_card_is_done() -> None:
    order = _order((1, V), (2, V))
    assert initial_focus(order, {1: True, 2: True}, None) == 1


def test_it_passes_over_a_card_done_via_another_source() -> None:
    assert initial_focus(CARDS, _done(1), None) == 2


def test_an_empty_review_opens_on_no_card() -> None:
    assert initial_focus(_order(), {}, None) is None


# --- the focus after a press --------------------------------------------------------------

def _pressed(
    *cards: tuple[int, bool, CandidateSection], sectioned: bool = True,
) -> tuple[ReviewOrder, dict[int, bool]]:
    """A held order and whether each card is done now, as the cards are listed."""
    order = _order(*((phrase_id, section) for phrase_id, _done, section in cards),
                   sectioned=sectioned)
    return order, {phrase_id: done for phrase_id, done, _section in cards}


def test_the_focus_takes_the_next_open_card_below_the_pressed_one() -> None:
    order, done = _pressed((1, False, R), (2, True, R), (5, False, R), (3, False, R))
    assert focus_after_press(order, 2, False, done) == 5


def test_the_focus_skips_done_cards_below_it() -> None:
    order, done = _pressed((1, False, R), (2, True, R), (4, True, R), (3, False, R))
    assert focus_after_press(order, 2, False, done) == 3


def test_the_focus_wraps_to_the_first_open_card_when_none_is_left_below() -> None:
    order, done = _pressed((1, False, R), (2, True, R), (3, True, V))
    assert focus_after_press(order, 2, False, done) == 1


def test_the_focus_never_lands_on_the_pressed_card() -> None:
    order, done = _pressed((2, True, R), (1, True, V))
    assert focus_after_press(order, 2, False, done) is None


def test_the_focus_stays_when_nothing_is_open() -> None:
    order, done = _pressed((1, True, V), (2, True, V))
    assert focus_after_press(order, 2, False, done) is None


def test_the_focus_stays_in_the_section_of_the_pressed_card() -> None:
    cards = ((1, True, R), (2, False, E), (3, True, V))
    assert focus_after_press(*_pressed(*cards)[:1], 1, False, _pressed(*cards)[1]) is None
    chronological, done = _pressed(*cards, sectioned=False)
    assert focus_after_press(chronological, 1, False, done) == 2


def test_the_focus_wraps_to_the_top_of_the_section_not_into_the_next_one() -> None:
    cards = ((1, False, R), (2, True, R), (4, False, E), (3, True, R))
    assert focus_after_press(*_pressed(*cards)[:1], 2, False, _pressed(*cards)[1]) == 1


def test_text_order_ignores_the_sections() -> None:
    order, done = _pressed(
        (1, False, R), (2, True, R), (4, False, E), (3, True, R), sectioned=False,
    )
    assert focus_after_press(order, 2, False, done) == 4


def test_the_focus_moves_on_when_the_pressed_card_became_done() -> None:
    order, done = _pressed((1, True, R), (2, False, R), (3, True, V))
    assert focus_after_press(order, 1, False, done) == 2


def test_the_focus_stays_when_the_card_was_done_already() -> None:
    order, done = _pressed((1, True, R), (2, False, R))
    assert focus_after_press(order, 1, True, done) is None


def test_the_focus_stays_when_the_card_is_open_again() -> None:
    order, done = _pressed((1, False, V), (2, False, R))
    assert focus_after_press(order, 1, True, done) is None


def test_the_focus_stays_when_the_card_is_gone_from_the_order() -> None:
    order, done = _pressed((2, False, R))
    assert focus_after_press(order, 1, False, {**done, 1: True}) is None


# --- the held order while the review is open ---------------------------------------------

# At the opening: 1 and 2 in Ready, 3 in Extra, 4 done already.
LOADED = _order((1, R), (2, R), (3, E), (4, V))


def _ids(order: ReviewOrder) -> list[int]:
    return list(order.phrase_ids)


def _fresh(*cards: tuple[int, CandidateSection]) -> list[HeldCard]:
    return list(_order(*cards).cards)


def test_a_pressed_card_keeps_its_place_and_section() -> None:
    after_press = _fresh((2, R), (3, E), (1, V), (4, V))
    kept = place_new(LOADED, after_press, ())
    assert _ids(kept) == [1, 2, 3, 4]
    assert kept.card(1) == HeldCard(1, 10, R)
    assert _rows(kept, {E, V}) == [1, 2, "extra-", 3, "reviewed-", 4]


def test_a_card_no_longer_shown_leaves_the_order() -> None:
    assert _ids(remove_cards(LOADED, {2})) == [1, 3, 4]
    assert remove_cards(LOADED, {99}) is LOADED


def test_a_new_card_goes_after_the_card_it_follows_in_the_fresh_order() -> None:
    fresh = _fresh((5, R), (1, R), (6, R), (2, R), (3, E), (4, V))
    placed = place_new(LOADED, fresh, {5, 6})
    assert _ids(placed) == [5, 1, 6, 2, 3, 4]
    assert placed.card(6) == HeldCard(6, 60, R)


def test_a_new_card_before_every_held_card_goes_to_the_top() -> None:
    fresh = _fresh((7, E), (2, R), (1, R), (3, E), (4, V))
    assert _ids(place_new(LOADED, fresh, {7})) == [7, 1, 2, 3, 4]


def test_a_run_of_new_cards_keeps_its_fresh_order() -> None:
    fresh = _fresh((1, R), (8, R), (7, R), (9, R), (2, R), (3, E), (4, V))
    assert _ids(place_new(LOADED, fresh, {7, 8, 9})) == [1, 8, 7, 9, 2, 3, 4]


def test_a_new_card_takes_its_fresh_section() -> None:
    fresh = _fresh((1, R), (9, E), (2, R), (3, E), (4, V))
    placed = place_new(LOADED, fresh, {9})
    assert placed.card(9) == HeldCard(9, 90, E)
    assert _rows(placed, {E, V}) == [1, 2, "extra-", 9, 3, "reviewed-", 4]


def test_the_first_order_is_the_fresh_one() -> None:
    fresh = _fresh((2, R), (3, E), (1, V))
    assert _ids(place_new(_order(), fresh, {1, 2, 3})) == [2, 3, 1]


def test_an_example_takes_the_place_of_the_card_it_replaces_with_its_own_section() -> None:
    replaced = replace_card(LOADED, 2, HeldCard(9, 20, E))
    assert _ids(replaced) == [1, 9, 3, 4]
    assert replaced.card(9) == HeldCard(9, 20, E)
    assert replaced.card(2) is None


# --- the focus when the current card is gone ------------------------------------------------

def test_a_gone_current_card_hands_the_focus_to_the_card_under_it() -> None:
    before = layout(_order((1, R), (2, R), (3, R)), frozenset(), 2)
    assert focus_after_removal(before, 2, {2}) == 3


def test_the_focus_goes_above_when_nothing_under_it_is_left() -> None:
    before = layout(_order((1, R), (2, R), (3, R)), frozenset(), 2)
    assert focus_after_removal(before, 2, {2, 3}) == 1


def test_no_focus_is_left_when_every_card_is_gone() -> None:
    before = layout(_order((1, R), (2, R)), frozenset(), 2)
    assert focus_after_removal(before, 2, {1, 2}) is None


def test_the_focus_passes_over_section_rows() -> None:
    before = layout(_order((1, R), (2, R), (5, E)), frozenset({E}), 2)
    assert focus_after_removal(before, 2, {2}) == 5


def test_the_focus_skips_a_folded_section() -> None:
    before = layout(_order((1, R), (2, R), (5, E)), frozenset(), 2)
    assert focus_after_removal(before, 2, {2}) == 1
