from enum import StrEnum

from backend.domain.value_objects.input_method import InputMethod


class ContentType(StrEnum):
    """What the content is for pipeline and review."""

    TEXT = "text"
    LYRICS = "lyrics"
    VIDEO = "video"


_MAPPING: dict[InputMethod, ContentType] = {
    InputMethod.TEXT_PASTED: ContentType.TEXT,
    InputMethod.LYRICS_PASTED: ContentType.LYRICS,
    InputMethod.SUBTITLES_FILE: ContentType.TEXT,
    InputMethod.VIDEO_FILE: ContentType.VIDEO,
    InputMethod.YOUTUBE_URL: ContentType.VIDEO,
}


def resolve_content_type(input_method: InputMethod) -> ContentType:
    """Resolve content type from input method. Pure function, no side effects."""
    return _MAPPING[input_method]
