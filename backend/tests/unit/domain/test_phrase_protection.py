"""Which phrases a rebuild may not delete (touched) and may never change (untouchable)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.services.card_view import is_protected, keeps_word
from backend.domain.services.phrase_protection import is_untouchable
from backend.domain.value_objects.card_choice import CardChoice, CardState, WordState
from backend.domain.value_objects.user_work import NO_USER_WORK, UserWork

from tests.rebuild_support import (
    COLLECTED,
    EXAMPLE,
    EXPORTED,
    MANUAL,
    MEANING,
    SELECTION,
    USER,
    row,
)

if TYPE_CHECKING:
    from backend.domain.value_objects.occurrence_row import OccurrenceRow


def test_a_plain_auto_phrase_is_not_untouchable() -> None:
    assert not is_untouchable(row(id=1, score=30.0))


def test_a_shown_mark_alone_does_not_protect() -> None:
    assert not is_untouchable(row(id=1, shown=SELECTION))


@pytest.mark.parametrize("open_card", [
    row(id=1, generation=MEANING),
    row(id=1, shows_polish=True),
    row(id=1, has_job=True),
])
def test_what_is_made_for_a_card_does_not_protect_it(open_card: OccurrenceRow) -> None:
    assert not is_untouchable(open_card)


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
def test_the_users_choice_and_work_protect_a_phrase(untouchable: OccurrenceRow) -> None:
    assert is_untouchable(untouchable)


# ── one definition: the card view's `is_protected` with the user's work ────────

PROTECTED_CHOICES = [CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP]
USER_WORK = {
    "edited": UserWork(edited=True),
    "picked": UserWork(picked=True),
    "added": UserWork(added=True),
}


@pytest.mark.parametrize("choice", PROTECTED_CHOICES)
def test_a_card_with_a_choice_is_protected(choice: CardChoice) -> None:
    assert is_protected(CardState(1, choice), NO_USER_WORK)
    assert is_untouchable(row(id=1, choice=choice))


def test_a_card_in_anki_is_protected_whatever_its_choice() -> None:
    assert is_protected(CardState(1, CardChoice.NONE, EXPORTED), NO_USER_WORK)
    assert is_untouchable(row(id=1, exported=True))


@pytest.mark.parametrize("work", USER_WORK.values(), ids=USER_WORK.keys())
def test_the_users_work_protects_an_open_card(work: UserWork) -> None:
    assert is_protected(CardState(1, CardChoice.NONE), work)


def test_an_open_card_without_the_users_work_is_not_protected() -> None:
    assert not is_protected(CardState(1, CardChoice.NONE), NO_USER_WORK)


@pytest.mark.parametrize(("built", "work"), [
    (row(id=1, edited=True), USER_WORK["edited"]),
    (row(id=1, shown=USER), USER_WORK["picked"]),
    (row(id=1, origin=MANUAL), USER_WORK["added"]),
    (row(id=1, origin=EXAMPLE), USER_WORK["added"]),
    (row(id=1, origin=COLLECTED), USER_WORK["added"]),
    (row(id=1, generation=MEANING, has_job=True, shown=SELECTION), NO_USER_WORK),
])
def test_a_row_reports_the_users_work_on_it(built: OccurrenceRow, work: UserWork) -> None:
    assert built.user_work == work


@pytest.mark.parametrize("work", USER_WORK.values(), ids=USER_WORK.keys())
def test_the_users_work_keeps_an_undecided_word(work: UserWork) -> None:
    word = WordState(1, "glare", "VERB", 1, (CardState(5, CardChoice.NONE),))
    assert keeps_word(word, {5: work})
    assert not keeps_word(word, {})
