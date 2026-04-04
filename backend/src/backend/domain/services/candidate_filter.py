from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.value_objects.cefr_level import CEFRLevel


class CandidateFilter:
    """Filters tokens to identify relevant learning candidates."""

    def is_relevant_token(self, token: TokenData) -> bool:
        """Check if a token is worth considering as a learning candidate.

        Excludes: punctuation, stop words, proper nouns, non-alphabetic tokens.
        """
        if token.is_punct:
            return False
        if token.is_stop:
            return False
        if token.is_propn:
            return False
        return token.is_alpha

    def is_above_user_level(self, cefr: CEFRLevel, user_level: CEFRLevel) -> bool:
        """Check if a word's CEFR level is above the user's current level."""
        return cefr.is_above(user_level)
