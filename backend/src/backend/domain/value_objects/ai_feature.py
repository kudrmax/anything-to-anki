from __future__ import annotations

from enum import StrEnum


class AIFeature(StrEnum):
    """What an AI call was made for — the unit token usage is broken down by."""

    MEANING_BATCH = "meaning_batch"
    MEANING_SINGLE = "meaning_single"
    MEANING_FOLLOW_UP = "meaning_follow_up"
    PHRASE_POLISH = "phrase_polish"
    TOPIC_TARGETS = "topic_targets"
