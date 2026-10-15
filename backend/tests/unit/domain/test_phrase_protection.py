"""Which phrases a rebuild may not delete (touched) and may never change (untouchable)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.services.phrase_protection import is_touched, is_untouchable

from tests.rebuild_support import COLLECTED, EXAMPLE, MANUAL, SELECTION, USER, row

if TYPE_CHECKING:
    from backend.domain.value_objects.occurrence_row import OccurrenceRow


def test_a_plain_auto_phrase_is_neither_touched_nor_untouchable() -> None:
    plain = row(id=1, score=0.3)
    assert not is_touched(plain, word_decided=False)
    assert not is_untouchable(plain)


def test_a_shown_mark_alone_touches_nothing() -> None:
    shown = row(id=1, shown=SELECTION)
    assert not is_touched(shown, word_decided=False)
    assert not is_untouchable(shown)


def test_a_shown_phrase_of_a_decided_word_is_touched_but_changeable() -> None:
    shown = row(id=1, shown=SELECTION)
    assert is_touched(shown, word_decided=True)
    assert not is_untouchable(shown)


def test_a_hidden_phrase_of_a_decided_word_is_not_touched() -> None:
    assert not is_touched(row(id=1), word_decided=True)


@pytest.mark.parametrize("touched", [
    row(id=1, has_results=True),
    row(id=1, has_job=True),
])
def test_results_and_a_job_touch_a_phrase_without_freezing_its_text(
    touched: OccurrenceRow,
) -> None:
    assert is_touched(touched, word_decided=False)
    assert not is_untouchable(touched)


@pytest.mark.parametrize("untouchable", [
    row(id=1, is_decision=True),
    row(id=1, skipped=True),
    row(id=1, exported=True),
    row(id=1, edited=True),
    row(id=1, shown=USER),
    row(id=1, origin=MANUAL),
    row(id=1, origin=EXAMPLE),
    row(id=1, origin=COLLECTED),
])
def test_untouchable_phrases_are_touched_too(untouchable: OccurrenceRow) -> None:
    assert is_untouchable(untouchable)
    assert is_touched(untouchable, word_decided=False)
