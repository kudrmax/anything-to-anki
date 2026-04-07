from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.enrichment_status import EnrichmentStatus


@dataclass(frozen=True)
class CandidateMedia:
    """Frozen value object representing the media enrichment for a candidate.

    1:1 with StoredCandidate. None when no extraction has been attempted yet.
    Holds screenshot/audio paths AND the subtitle timecodes used to extract them.
    """

    candidate_id: int
    screenshot_path: str | None
    audio_path: str | None
    start_ms: int | None
    end_ms: int | None
    status: EnrichmentStatus
    error: str | None
    generated_at: datetime | None
