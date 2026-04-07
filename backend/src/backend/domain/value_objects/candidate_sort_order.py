from __future__ import annotations

from enum import Enum


class CandidateSortOrder(Enum):
    """How candidates should be ordered when fetched or enqueued.

    RELEVANCE: sweet-spot first, then by zipf frequency desc, then CEFR desc.
        This is the default — surfaces words most worth learning first.
    CHRONOLOGICAL: in the order they appear in the source text (id asc).
        Useful for sources where text order is meaningful (lyrics, subtitles).
    """

    RELEVANCE = "relevance"
    CHRONOLOGICAL = "chronological"
