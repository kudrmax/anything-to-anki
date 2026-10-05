from __future__ import annotations

from enum import StrEnum


class MissingCardPart(StrEnum):
    """A part a card needs before it is ready for Anki."""

    MEANING = "meaning"
    AUDIO = "audio"
    """The phrase spoken: a clip cut from the video or TTS."""
