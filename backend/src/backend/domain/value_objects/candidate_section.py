from __future__ import annotations

from enum import Enum


class CandidateSection(Enum):
    """Where a card stands in review, top to bottom.

    READY: only the target is new. EXTRA: other words of the phrase are new
    too. PROBABLY_KNOWN: the target is frequent enough to be known, or junk.
    """

    READY = "ready"
    EXTRA = "extra"
    PROBABLY_KNOWN = "probably_known"
