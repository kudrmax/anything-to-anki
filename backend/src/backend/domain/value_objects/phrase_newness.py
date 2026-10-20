from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.user_knowledge import Newness, is_new_at

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class NewnessOfWord:
    lemma: str
    zipf: float
    newness: Newness


@dataclass(frozen=True)
class PhraseNewness:
    """The words of a phrase besides the target, each with its newness, in phrase order:
    enough to tell the new words at any frequent word threshold."""

    words: tuple[NewnessOfWord, ...]

    @classmethod
    def of(cls, words: Iterable[tuple[str, float, Newness]]) -> PhraseNewness:
        """`words`: lemma, zipf and newness of each word."""
        return cls(tuple(NewnessOfWord(*word) for word in words))

    def new_lemmas(self, step: float | None) -> list[str]:
        """Lemmas new at the threshold `step`, once each, in phrase order."""
        found: list[str] = []
        for word in self.words:
            if word.lemma not in found and is_new_at(word.newness, word.zipf, step):
                found.append(word.lemma)
        return found

    def count(self, step: float | None) -> int:
        return len(self.new_lemmas(step))


NO_NEWNESS = PhraseNewness(())
