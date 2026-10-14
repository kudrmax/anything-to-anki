"""Which phrase of a word the selection shows, and when it leaves the shown one alone."""
from __future__ import annotations

from backend.domain.services.phrase_selection import SelectionChange, select_phrases

from tests.rebuild_support import COLLECTED, EXAMPLE, MANUAL, SELECTION, USER, row


def test_frozen_decision_phrase_keeps_selection() -> None:
    a = row(id=1, score=0.5, shown=SELECTION, is_decision=True)
    b = row(id=2, score=0.1)
    assert select_phrases([a, b], word_decided=True, include_open=True).set_selection is None


def test_results_freeze_without_include_open_only() -> None:
    a = row(id=1, score=0.5, shown=SELECTION, has_results=True)
    b = row(id=2, score=0.1)
    assert select_phrases([a, b], False, include_open=False).set_selection is None
    assert select_phrases([a, b], False, include_open=True).set_selection == 2


def test_user_shown_auto_blocks_selection() -> None:
    a = row(id=1, score=0.1)
    b = row(id=2, score=0.9, shown=USER, replaces=True)
    assert select_phrases([a, b], False, False).set_selection is None


def test_a_user_shown_auto_beside_a_lost_selection_card_does_not_block_it() -> None:
    a = row(id=1, score=0.1)
    b = row(id=2, score=0.9, shown=USER)
    assert select_phrases([a, b], False, False).set_selection == 1


def test_an_example_that_replaced_a_manual_card_does_not_block_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER)
    auto = row(id=2, score=0.1)
    assert select_phrases([example, auto], False, False).set_selection == 2


def test_a_replacing_phrase_no_longer_shown_does_not_block_selection() -> None:
    example = row(id=1, origin=EXAMPLE, replaces=True)
    auto = row(id=2, score=0.1)
    assert select_phrases([example, auto], False, False).set_selection == 2


def test_a_replaced_selection_card_clears_a_loose_selection_mark() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER, replaces=True)
    loose = row(id=2, score=0.1, shown=SELECTION)
    assert select_phrases([example, loose], False, False) == SelectionChange(
        clear_selection=(2,),
    )


def test_skipped_never_selected() -> None:
    a = row(id=1, score=0.1, skipped=True)
    b = row(id=2, score=0.9)
    assert select_phrases([a, b], False, False).set_selection == 2


def test_the_best_phrase_is_selected_and_the_old_mark_cleared() -> None:
    old = row(id=1, score=0.5, shown=SELECTION)
    best = row(id=2, score=0.1)
    assert select_phrases([old, best], False, False) == SelectionChange(
        set_selection=2, clear_selection=(1,),
    )


def test_an_already_selected_best_phrase_is_no_change() -> None:
    best = row(id=1, score=0.1, shown=SELECTION)
    worse = row(id=2, score=0.5)
    assert select_phrases([best, worse], False, False).is_empty


def test_a_tie_goes_to_the_phrase_read_first() -> None:
    later = row(id=1, line=5, score=0.2)
    earlier = row(id=2, line=1, score=0.2)
    assert select_phrases([later, earlier], False, False).set_selection == 2


def test_a_phrase_without_a_score_goes_last() -> None:
    unscored = row(id=1, line=0, score=None)
    scored = row(id=2, line=1, score=9.0)
    assert select_phrases([unscored, scored], False, False).set_selection == 2


def test_a_job_freezes_like_results() -> None:
    a = row(id=1, score=0.5, shown=SELECTION, has_job=True)
    b = row(id=2, score=0.1)
    assert select_phrases([a, b], False, include_open=False).is_empty
    assert select_phrases([a, b], False, include_open=True).set_selection == 2


def test_skip_edit_and_export_freeze_even_with_include_open() -> None:
    for frozen in (
        row(id=1, score=0.5, shown=SELECTION, skipped=True),
        row(id=1, score=0.5, shown=SELECTION, edited=True),
        row(id=1, score=0.5, shown=SELECTION, exported=True),
    ):
        b = row(id=2, score=0.1)
        assert select_phrases([frozen, b], False, include_open=True).is_empty


def test_a_frozen_mark_wins_over_a_second_selection_mark() -> None:
    frozen = row(id=1, score=0.5, shown=SELECTION, has_results=True)
    loose = row(id=2, score=0.1, shown=SELECTION)
    assert select_phrases([frozen, loose], False, False) == SelectionChange(
        set_selection=None, clear_selection=(2,),
    )


def test_a_decided_word_keeps_its_marks_as_they_are() -> None:
    shown = row(id=1, score=0.5, shown=SELECTION)
    better = row(id=2, score=0.1)
    assert select_phrases([shown, better], word_decided=True, include_open=True).is_empty


def test_an_example_that_replaced_the_selection_card_leaves_no_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER, replaces=True)
    auto = row(id=2, score=0.1)
    assert select_phrases([example, auto], False, False).is_empty


def test_an_example_beside_a_selection_card_keeps_one_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER)
    old = row(id=2, score=0.5, shown=SELECTION)
    best = row(id=3, score=0.1)
    assert select_phrases([example, old, best], False, False) == SelectionChange(
        set_selection=3, clear_selection=(2,),
    )


def test_a_manual_phrase_is_extra_to_the_selection() -> None:
    manual = row(id=1, origin=MANUAL, shown=USER)
    auto = row(id=2, score=0.4)
    assert select_phrases([manual, auto], False, False).set_selection == 2


def test_a_collected_phrase_is_never_selected_nor_cleared() -> None:
    collected = row(id=1, origin=COLLECTED, shown=USER, score=0.0)
    assert select_phrases([collected], False, False).is_empty


def test_only_skipped_auto_phrases_select_nothing() -> None:
    skipped = row(id=1, score=0.0, skipped=True)
    assert select_phrases([skipped], False, False).is_empty
