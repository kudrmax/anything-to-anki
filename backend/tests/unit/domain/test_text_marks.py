"""Which targets of the shown phrases are marked where they would overlap."""
from __future__ import annotations

from backend.domain.services.text_marks import PlacedMark, marks_shown


def test_a_phrasal_verb_over_its_verb_keeps_the_longer_mark() -> None:
    verb, phrasal = PlacedMark(1, 3, 7), PlacedMark(2, 3, 10)

    assert marks_shown([verb, phrasal]) == [phrasal]


def test_the_first_start_wins() -> None:
    first, later = PlacedMark(2, 0, 5), PlacedMark(1, 3, 9)

    assert marks_shown([later, first]) == [first]


def test_a_tie_is_broken_by_phrase_id() -> None:
    older, newer = PlacedMark(1, 4, 8), PlacedMark(2, 4, 8)

    assert marks_shown([newer, older]) == [older]


def test_a_mark_inside_a_kept_one_is_dropped() -> None:
    outer, inner, after = PlacedMark(1, 0, 20), PlacedMark(2, 5, 8), PlacedMark(3, 20, 25)

    assert marks_shown([inner, after, outer]) == [outer, after]
