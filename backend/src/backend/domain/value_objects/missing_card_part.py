from __future__ import annotations

from enum import StrEnum


class MissingCardPart(StrEnum):
    """A part a card needs before it is ready for Anki."""

    MEANING = "meaning"
    AUDIO = "audio"
    """The phrase spoken: a clip cut from the video or TTS."""
    CLOZE = "cloze"
    """The words a cloze card hides: the decision is a cloze, its phrase has no markup."""
