from __future__ import annotations

from enum import Enum


class CandidateSortOrder(Enum):
    """How candidates should be ordered when fetched or enqueued.

    RELEVANCE: cards most worth learning first, probably useless ones at
        the bottom (see ``sort_by_relevance``). This is the default.
    CHRONOLOGICAL: in the order they appear in the source text (id asc).
        Useful for sources where text order is meaningful (lyrics, subtitles).
    KEY_WORDS: words the text leans on most first (see ``sort_by_key_words``).
        Useful to prepare before reading a hard text, e.g. a book chapter.
    """

    RELEVANCE = "relevance"
    CHRONOLOGICAL = "chronological"
    KEY_WORDS = "key_words"
