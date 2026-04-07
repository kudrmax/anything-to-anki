from __future__ import annotations

from enum import Enum


class ProcessingStage(Enum):
    """Current stage within the PROCESSING status."""

    CLEANING_SOURCE = "cleaning_source"
    ANALYZING_TEXT = "analyzing_text"
    MAPPING_TIMECODES = "mapping_timecodes"
