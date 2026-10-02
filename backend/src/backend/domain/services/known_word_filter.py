from __future__ import annotations


class KnownWordFilter:
    """Checks whether a word is known.

    A word is known as a whole: marking it known in one part of speech
    covers every other one ("divorce" the noun hides "divorce" the verb).
    """

    def __init__(self, known_pairs: set[tuple[str, str | None]]) -> None:
        self._known_lemmas = frozenset(lemma.lower() for lemma, _ in known_pairs)

    @property
    def known_lemmas(self) -> frozenset[str]:
        return self._known_lemmas

    def is_known(self, lemma: str) -> bool:
        return lemma.lower() in self._known_lemmas
