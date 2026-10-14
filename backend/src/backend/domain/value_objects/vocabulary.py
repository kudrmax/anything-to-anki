from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vocabulary:
    """What the user said they know and don't know, word by word.

    A word is known as a whole: marking it in one part of speech covers every
    other one. A word in both lists is unknown: the user's "I don't know it"
    is never overridden.
    """

    known: frozenset[str]
    unknown: frozenset[str]

    @staticmethod
    def of(known: set[str] | frozenset[str], unknown: set[str] | frozenset[str]) -> Vocabulary:
        return Vocabulary(
            known=frozenset(lemma.lower() for lemma in known),
            unknown=frozenset(lemma.lower() for lemma in unknown),
        )

    def is_known(self, lemma: str) -> bool:
        key = lemma.lower()
        return key in self.known and key not in self.unknown

    def is_unknown(self, lemma: str) -> bool:
        return lemma.lower() in self.unknown


EMPTY_VOCABULARY = Vocabulary(known=frozenset(), unknown=frozenset())
