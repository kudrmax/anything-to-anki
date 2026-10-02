from __future__ import annotations

from enum import Enum


class CandidateSortOrder(Enum):
    """How candidates should be ordered when fetched or enqueued.

    RELEVANCE: cards most worth learning first, probably useless ones at
        the bottom (see ``sort_by_relevance``). This is the default.
    CHRONOLOGICAL: in the order they appear in the source text (id asc).
        Useful for sources where text order is meaningful (lyrics, subtitles).
    """

    RELEVANCE = "relevance"
    CHRONOLOGICAL = "chronological"
