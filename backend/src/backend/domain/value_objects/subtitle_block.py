from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleBlock:
    """One subtitle entry with its timecodes and position in the cleaned text."""

    start_ms: int
    end_ms: int
    char_start: int  # start offset in cleaned_text (inclusive)
    char_end: int    # end offset in cleaned_text (exclusive)
