from __future__ import annotations

from enum import Enum


class ProcessingStage(Enum):
    """What a running process of a source is doing now."""

    ANALYZING_TEXT = "analyzing_text"
    COLLECTING_PHRASES = "collecting_phrases"
