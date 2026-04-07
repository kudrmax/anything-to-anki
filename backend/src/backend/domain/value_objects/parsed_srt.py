from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.subtitle_block import SubtitleBlock


@dataclass(frozen=True)
class ParsedSrt:
    """Result of structured SRT parsing: cleaned text + per-block timecodes."""

    text: str
    blocks: tuple[SubtitleBlock, ...] = ()
