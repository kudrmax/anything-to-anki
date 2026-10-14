from __future__ import annotations

from enum import StrEnum


class OccurrenceOrigin(StrEnum):
    """How a phrase came to be an occurrence of a word."""

    AUTO = "auto"
    MANUAL = "manual"
    EXAMPLE = "example"
    COLLECTED = "collected"


class ShownBy(StrEnum):
    """Who put a phrase in front of the user."""

    SELECTION = "selection"
    USER = "user"


class DecisionKind(StrEnum):
    """What the phrase of the decision becomes in Anki."""

    LEARN = "learn"
    CLOZE = "cloze"
