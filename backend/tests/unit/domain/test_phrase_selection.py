"""Which phrase of a word the selection shows, and when it leaves the shown one alone."""
from __future__ import annotations

from backend.domain.services.fragment_selection.scoring.scorer import FragmentScore
from backend.domain.services.phrase_selection import (
    UNSCORED,
    SelectionChange,
    SelectionScore,
    select_phrases,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import Vocabulary

from tests.rebuild_support import COLLECTED, EXAMPLE, MANUAL, MEANING, SELECTION, USER, row

SCORE = SelectionScore(knowledge=None, weight_unknown=1)
NEW_WORD_TEXT = "He glared at the gargoyle."


def _knowing(*known: str) -> UserKnowledge:
    return UserKnowledge(
        vocabulary=Vocabulary.of(known=set(known), unknown=set()),
        user_level=CEFRLevel.B1,
        frequent_zipf=None,
    )


def _score(*, unknowns: int, content: int = 5) -> float:
    return FragmentScore(
        length_overflow=0, incomplete=0, boundary_penalty=0, unknowns=unknowns,
        content_count=content,
    ).as_number()


def test_frozen_decision_phrase_keeps_selection() -> None:
    a = row(id=1, score=50.0, shown=SELECTION, is_decision=True)
    b = row(id=2, score=10.0)
    assert select_phrases([a, b], word_decided=True, score=SCORE).set_selection is None


def test_what_was_made_for_a_card_does_not_hold_its_selection() -> None:
    a = row(id=1, score=50.0, shown=SELECTION, generation=MEANING)
    b = row(id=2, score=10.0)
    assert select_phrases([a, b], False, SCORE).set_selection == 2


def test_user_shown_auto_blocks_selection() -> None:
    a = row(id=1, score=10.0)
    b = row(id=2, score=90.0, shown=USER, replaces=True)
    assert select_phrases([a, b], False, SCORE).set_selection is None


def test_a_user_shown_auto_beside_a_lost_selection_card_does_not_block_it() -> None:
    a = row(id=1, score=10.0)
    b = row(id=2, score=90.0, shown=USER)
    assert select_phrases([a, b], False, SCORE).set_selection == 1


def test_an_example_that_replaced_a_manual_card_does_not_block_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER)
    auto = row(id=2, score=10.0)
    assert select_phrases([example, auto], False, SCORE).set_selection == 2


def test_a_replacing_phrase_no_longer_shown_does_not_block_selection() -> None:
    example = row(id=1, origin=EXAMPLE, replaces=True)
    auto = row(id=2, score=10.0)
    assert select_phrases([example, auto], False, SCORE).set_selection == 2


def test_a_replaced_selection_card_clears_a_loose_selection_mark() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER, replaces=True)
    loose = row(id=2, score=10.0, shown=SELECTION)
    assert select_phrases([example, loose], False, SCORE) == SelectionChange(
        clear_selection=(2,),
    )


def test_skipped_never_selected() -> None:
    a = row(id=1, score=10.0, skipped=True)
    b = row(id=2, score=90.0)
    assert select_phrases([a, b], False, SCORE).set_selection == 2


def test_the_best_phrase_is_selected_and_the_old_mark_cleared() -> None:
    old = row(id=1, score=50.0, shown=SELECTION)
    best = row(id=2, score=10.0)
    assert select_phrases([old, best], False, SCORE) == SelectionChange(
        set_selection=2, clear_selection=(1,),
    )


def test_an_already_selected_best_phrase_is_no_change() -> None:
    best = row(id=1, score=10.0, shown=SELECTION)
    worse = row(id=2, score=50.0)
    assert select_phrases([best, worse], False, SCORE).is_empty


def test_a_tie_goes_to_the_phrase_read_first() -> None:
    later = row(id=1, line=5, score=20.0)
    earlier = row(id=2, line=1, score=20.0)
    assert select_phrases([later, earlier], False, SCORE).set_selection == 2


def test_a_phrase_without_a_score_goes_last() -> None:
    unscored = row(id=1, line=0, score=None)
    scored = row(id=2, line=1, score=900.0)
    assert select_phrases([unscored, scored], False, SCORE).set_selection == 2


def test_a_job_holds_the_selection() -> None:
    a = row(id=1, score=50.0, shown=SELECTION, has_job=True)
    b = row(id=2, score=10.0)
    assert select_phrases([a, b], False, SCORE).is_empty


def test_skip_edit_and_export_freeze() -> None:
    for frozen in (
        row(id=1, score=50.0, shown=SELECTION, skipped=True),
        row(id=1, score=50.0, shown=SELECTION, edited=True),
        row(id=1, score=50.0, shown=SELECTION, exported=True),
    ):
        b = row(id=2, score=10.0)
        assert select_phrases([frozen, b], False, SCORE).is_empty


def test_a_frozen_mark_wins_over_a_second_selection_mark() -> None:
    frozen = row(id=1, score=50.0, shown=SELECTION, has_job=True)
    loose = row(id=2, score=10.0, shown=SELECTION)
    assert select_phrases([frozen, loose], False, SCORE) == SelectionChange(
        set_selection=None, clear_selection=(2,),
    )


def test_a_decided_word_keeps_its_marks_as_they_are() -> None:
    shown = row(id=1, score=50.0, shown=SELECTION)
    better = row(id=2, score=10.0)
    assert select_phrases([shown, better], word_decided=True, score=SCORE).is_empty


def test_an_example_that_replaced_the_selection_card_leaves_no_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER, replaces=True)
    auto = row(id=2, score=10.0)
    assert select_phrases([example, auto], False, SCORE).is_empty


def test_an_example_beside_a_selection_card_keeps_one_selection() -> None:
    example = row(id=1, origin=EXAMPLE, shown=USER)
    old = row(id=2, score=50.0, shown=SELECTION)
    best = row(id=3, score=10.0)
    assert select_phrases([example, old, best], False, SCORE) == SelectionChange(
        set_selection=3, clear_selection=(2,),
    )


def test_a_manual_phrase_is_extra_to_the_selection() -> None:
    manual = row(id=1, origin=MANUAL, shown=USER)
    auto = row(id=2, score=40.0)
    assert select_phrases([manual, auto], False, SCORE).set_selection == 2


def test_a_collected_phrase_is_never_selected_nor_cleared() -> None:
    collected = row(id=1, origin=COLLECTED, shown=USER, score=0.0)
    assert select_phrases([collected], False, SCORE).is_empty


def test_only_skipped_auto_phrases_select_nothing() -> None:
    skipped = row(id=1, score=0.0, skipped=True)
    assert select_phrases([skipped], False, SCORE).is_empty


def test_a_phrase_is_scored_by_the_new_words_it_has_now() -> None:
    stored = row(id=1, score=_score(unknowns=0), text=NEW_WORD_TEXT, new=["gargoyle"])
    score = SelectionScore(knowledge=_knowing(), weight_unknown=3)
    assert score.of(stored) == _score(unknowns=3)


def test_a_word_learned_since_the_cut_no_longer_counts() -> None:
    stored = row(id=1, score=_score(unknowns=1), text=NEW_WORD_TEXT, new=["gargoyle"])
    score = SelectionScore(knowledge=_knowing("gargoyle"), weight_unknown=1)
    assert score.of(stored) == _score(unknowns=0)


def test_the_target_is_not_one_of_the_new_words() -> None:
    stored = row(id=1, score=_score(unknowns=0), text="Gargoyles glare.", new=["gargoyles"])
    assert SelectionScore(knowledge=_knowing(), weight_unknown=1).of(stored) == _score(
        unknowns=0,
    )


def test_a_phrase_without_a_cut_score_stays_unscored() -> None:
    assert SCORE.of(row(id=1, score=None)) == UNSCORED


def test_the_selection_moves_to_the_phrase_that_got_easier() -> None:
    shown = row(
        id=1, line=1, score=_score(unknowns=0, content=4), shown=SELECTION,
        text=NEW_WORD_TEXT, new=["gargoyle"],
    )
    easier = row(id=2, line=2, score=_score(unknowns=1, content=6), new=[])
    change = select_phrases([shown, easier], False, SelectionScore(_knowing(), 1))
    assert change == SelectionChange(set_selection=2, clear_selection=(1,))
