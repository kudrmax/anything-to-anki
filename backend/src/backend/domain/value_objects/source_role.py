from enum import StrEnum


class SourceRole(StrEnum):
    """What a source is in the app: content the user added, a topic, or the saved phrases."""

    CONTENT = "content"
    TOPIC = "topic"
    SAVED_PHRASES = "saved_phrases"
