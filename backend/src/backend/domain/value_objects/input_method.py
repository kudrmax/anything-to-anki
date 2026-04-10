from enum import StrEnum


class InputMethod(StrEnum):
    """How content was ingested into the system."""

    TEXT_PASTED = "text_pasted"
    LYRICS_PASTED = "lyrics_pasted"
    SUBTITLES_FILE = "subtitles_file"
    VIDEO_FILE = "video_file"
    YOUTUBE_URL = "youtube_url"
