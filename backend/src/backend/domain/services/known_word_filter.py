from __future__ import annotations


class KnownWordFilter:
    """Checks whether a word is known, considering wildcard (pos=None) entries."""

    def __init__(self, known_pairs: set[tuple[str, str | None]]) -> None:
        self._known_pairs = known_pairs

    def is_known(self, lemma: str, pos: str) -> bool:
        return (lemma, pos) in self._known_pairs or (lemma, None) in self._known_pairs
