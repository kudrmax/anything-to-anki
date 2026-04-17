from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
    from backend.domain.value_objects.candidate_status import CandidateStatus


@dataclass
class StoredCandidate:
    """A word candidate persisted after source processing.

    `meaning` and `media` are nested enrichment objects (1:1) that may be None
    if no generation/extraction has been attempted yet. They live in their own
    tables (`candidate_meanings`, `candidate_media`) but are loaded together
    with the candidate by the repository.
    """

    source_id: int
    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    fragment_purity: str
    occurrences: int
    status: CandidateStatus
    surface_form: str | None = None
    is_phrasal_verb: bool = False
    has_custom_context_fragment: bool = False
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    id: int | None = None
    cefr_breakdown: CEFRBreakdown | None = None
