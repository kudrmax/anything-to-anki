from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

from backend.domain.value_objects.user_knowledge import Newness, is_new_at

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


class NewnessOfWord(NamedTuple):
    """A tuple, not a dataclass: a frequent lemma's phrases hold tens of thousands of words,
    made anew at every change of the lemma."""

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
        """How many lemmas are new at the threshold `step`."""
        return len({word.lemma for word in self.words if is_new_at(word.newness, word.zipf, step)})

    def counts(self, steps: Sequence[float | None]) -> tuple[int, ...]:
        """`count` at each of `steps`, the words read once: a lemma always new counts at
        every step; one new only if rare counts where its rarest word is new."""
        always: set[str] = set()
        rarest: dict[str, float] = {}
        for word in self.words:
            if word.newness is Newness.ALWAYS:
                always.add(word.lemma)
            elif word.newness is Newness.IF_RARE:
                rarest[word.lemma] = min(rarest.get(word.lemma, word.zipf), word.zipf)
        rare = [zipf for lemma, zipf in rarest.items() if lemma not in always]
        return tuple(
            len(always) + sum(is_new_at(Newness.IF_RARE, zipf, step) for zipf in rare)
            for step in steps
        )


NO_NEWNESS = PhraseNewness(())
