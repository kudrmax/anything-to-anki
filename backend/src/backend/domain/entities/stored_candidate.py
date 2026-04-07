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
    meaning: str | None = None
    ipa: str | None = None
    is_phrasal_verb: bool = False
    media_start_ms: int | None = None    # start of covering subtitle range
    media_end_ms: int | None = None      # end of covering subtitle range
    screenshot_path: str | None = None   # absolute path to generated screenshot
    audio_path: str | None = None        # absolute path to generated audio clip
    id: int | None = None
