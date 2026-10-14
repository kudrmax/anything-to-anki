from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.phrase import Word
    from backend.domain.value_objects.vocabulary import Vocabulary


@dataclass(frozen=True)
class UserKnowledge:
    """What decides whether a word is new to the user, right now.

    `frequent_zipf`: words at least this frequent count as known; None — frequency is ignored.
    """

    vocabulary: Vocabulary
    user_level: CEFRLevel
    frequent_zipf: float | None

    def is_new(self, word: Word) -> bool:
        """New if the user said they don't know it, or it is a content word above the user's
        level, not frequent, and not one they said they know."""
        if self.vocabulary.is_unknown(word.lemma):
            return True
        if not word.content or self.vocabulary.is_known(word.lemma):
            return False
        frequent = self.frequent_zipf is not None and word.zipf >= self.frequent_zipf
        return not frequent and word.level.is_above(self.user_level)
