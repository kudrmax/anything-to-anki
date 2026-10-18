from __future__ import annotations

from enum import StrEnum


class CardNote(StrEnum):
    """Why a card shows what it shows, beside its buttons."""

    DECIDED_ON_OTHER_CARD = "decided_on_other_card"
    KNOWN_ELSEWHERE = "known_elsewhere"
    LEARNING_ELSEWHERE = "learning_elsewhere"
    LEARN_ELSEWHERE = "learn_elsewhere"
    IN_ANKI = "in_anki"
    KNOWN_BY_TIMER = "known_by_timer"
    KNOWN_BY_LIST = "known_by_list"
