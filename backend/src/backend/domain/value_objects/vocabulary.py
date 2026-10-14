from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class Vocabulary:
    """What the user said they know and don't know, and what they are learning, word by word.

    A word is known as a whole: marking it in one part of speech covers every
    other one. Priority: unknown > known > learning — the user's "I don't know it"
    is never overridden, and a known word is not being learned.
    """

    known: frozenset[str]
    unknown: frozenset[str]
    learning: frozenset[str] = frozenset()

    @staticmethod
    def of(
        known: set[str] | frozenset[str],
        unknown: set[str] | frozenset[str],
        learning: set[str] | frozenset[str] = frozenset(),
    ) -> Vocabulary:
        return Vocabulary(
            known=frozenset(lemma.lower() for lemma in known),
            unknown=frozenset(lemma.lower() for lemma in unknown),
            learning=frozenset(lemma.lower() for lemma in learning),
        )

    def is_known(self, lemma: str) -> bool:
        key = lemma.lower()
        return key in self.known and key not in self.unknown

    def is_unknown(self, lemma: str) -> bool:
        return lemma.lower() in self.unknown

    def is_learning(self, lemma: str) -> bool:
        key = lemma.lower()
        return key in self.learning and key not in self.known and key not in self.unknown

    def is_known_or_learning(self, lemma: str) -> bool:
        """Not a new candidate: the user knows it or already learns it."""
        return self.is_known(lemma) or self.is_learning(lemma)

    def without_learning(self, lemmas: Iterable[str]) -> Vocabulary:
        dropped = {lemma.lower() for lemma in lemmas}
        return Vocabulary(self.known, self.unknown, self.learning - dropped)


EMPTY_VOCABULARY = Vocabulary(known=frozenset(), unknown=frozenset())
