from enum import StrEnum


class Format(StrEnum):
    """How the input is laid out; one reader per format."""

    PLAIN = "plain"
    MARKDOWN = "markdown"
    HTML = "html"
    EPUB = "epub"
    SRT = "srt"
    VIDEO_FILE = "video_file"
    YOUTUBE = "youtube"
