from enum import StrEnum


class InputKind(StrEnum):
    """What the Add screen input becomes once added."""

    SOURCE = "source"
    TOPIC = "topic"
    PHRASE = "phrase"
