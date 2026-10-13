from __future__ import annotations

from enum import Enum


class ProcessingStage(Enum):
    """Current stage within the PROCESSING status."""

    ANALYZING_TEXT = "analyzing_text"
    COLLECTING_PHRASES = "collecting_phrases"
