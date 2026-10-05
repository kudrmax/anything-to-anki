from __future__ import annotations

from enum import StrEnum


class ClozeHintKind(StrEnum):
    """What the cloze card shows next to the gap to make the answer unambiguous."""

    NONE = "none"
    TRANSLATION = "translation"
    SYNONYMS = "synonyms"
    FIRST_LETTER = "first_letter"
    CUSTOM = "custom"
