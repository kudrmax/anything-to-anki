from __future__ import annotations

import pytest
from backend.domain.value_objects.note_maturity import MATURE_INTERVAL_DAYS, NoteCards, is_mature

pytestmark = pytest.mark.unit


def test_a_note_whose_cards_all_reached_the_interval_is_mature() -> None:
    assert is_mature(NoteCards(intervals=(MATURE_INTERVAL_DAYS, 40), suspended=0)) is True


def test_one_young_card_keeps_the_note_young() -> None:
    assert is_mature(NoteCards(intervals=(40, MATURE_INTERVAL_DAYS - 1), suspended=0)) is False


def test_a_note_without_cards_is_not_mature() -> None:
    assert is_mature(NoteCards(intervals=(), suspended=0)) is False


def test_a_note_with_only_suspended_cards_is_not_mature() -> None:
    assert is_mature(NoteCards(intervals=(), suspended=2)) is False


def test_suspended_cards_do_not_hold_a_mature_note_back() -> None:
    assert is_mature(NoteCards(intervals=(30,), suspended=1)) is True


def test_a_card_in_learning_is_not_mature() -> None:
    """Anki gives a card in (re)learning a negative interval, in seconds."""
    assert is_mature(NoteCards(intervals=(-600, 30), suspended=0)) is False


def test_the_threshold_is_the_anki_standard() -> None:
    assert MATURE_INTERVAL_DAYS == 21
