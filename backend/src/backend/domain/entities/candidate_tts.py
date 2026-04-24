from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class CandidateTTS:
    """TTS audio enrichment for a candidate (1:1).

    Holds path to generated TTS audio file (M4A).
    None path means no TTS has been generated yet.
    """

    candidate_id: int
    audio_path: str | None
    generated_at: datetime | None
