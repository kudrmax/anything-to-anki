from __future__ import annotations

from enum import StrEnum


class CardFillSkip(StrEnum):
    """Why a missing part of an export card can't be generated now."""

    VIDEO_NOT_DOWNLOADED = "video_not_downloaded"
    """The audio clip is cut from the video, and the source has no video file."""
    VIDEO_DOWNLOADING = "video_downloading"
    NO_PHRASE_TIME = "no_phrase_time"
    """The audio clip needs the time of the phrase in the video, and the phrase has none."""
    SOURCE_BUSY = "source_busy"
    """A long operation (processing, Rebuild) holds the source."""
    CLOZE_NEEDS_CHOICE = "cloze_needs_choice"
    """The words a cloze hides are the user's choice, nothing generates them."""
