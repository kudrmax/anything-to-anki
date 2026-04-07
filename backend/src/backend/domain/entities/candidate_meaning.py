from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.domain.value_objects.enrichment_status import EnrichmentStatus


@dataclass(frozen=True)
class CandidateMeaning:
    """Frozen value object representing the meaning enrichment for a candidate.

    1:1 with StoredCandidate. None when no generation has been attempted yet.
    """

    candidate_id: int
    meaning: str | None
    ipa: str | None
    status: EnrichmentStatus
    error: str | None
    generated_at: datetime | None
