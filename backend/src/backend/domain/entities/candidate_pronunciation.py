from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class CandidatePronunciation:
    """Pronunciation audio enrichment for a candidate (1:1).

    Holds paths to downloaded US/UK mp3 files from a dictionary source.
    None paths mean no audio available for that variant.
    """

    candidate_id: int
    us_audio_path: str | None
    uk_audio_path: str | None
    generated_at: datetime | None
