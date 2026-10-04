from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class CandidateMedia:
    """Frozen value object representing the media enrichment for a candidate.

    1:1 with StoredCandidate. None when no extraction has been attempted yet.
    Holds screenshot/audio paths AND the subtitle timecodes used to extract them.
    `screenshot_path` is the card's picture: a video frame, or a picture of the
    target the user picked instead.
    """

    candidate_id: int
    screenshot_path: str | None
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    generated_at: datetime | None
