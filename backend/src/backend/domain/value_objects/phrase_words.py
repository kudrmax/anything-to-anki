from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseWord:
    """A word of a card's phrase besides the target.

    `rare`: above the user's level and not frequent, so unknown unless the
    user said they know it.
    """

    lemma: str
    rare: bool


@dataclass(frozen=True)
class PhraseWords:
    """The words of a card's phrase, and the phrase they were read from."""

    phrase: str
    words: tuple[PhraseWord, ...]

    def is_of(self, phrase: str) -> bool:
        return self.phrase == phrase
