from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicTargetDraft:
    """A target proposed by AI for a topic, before it is attached to a source."""

    phrase: str
    example: str
