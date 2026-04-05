from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.candidate_status import CandidateStatus


@dataclass
class StoredCandidate:
    """A word candidate persisted after source processing."""

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
    ai_meaning: str | None = None
    is_phrasal_verb: bool = False
    id: int | None = None
