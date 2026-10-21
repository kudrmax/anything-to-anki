"""A card's values at every frequent word threshold, one per step of THRESHOLD_STEPS, in
its order: the user may switch the threshold, and nothing is computed again."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS, step_index

if TYPE_CHECKING:
    from backend.domain.value_objects.candidate_section import CandidateSection


def _check_length(values: tuple[object, ...], name: str) -> None:
    if len(values) != len(THRESHOLD_STEPS):
        msg = f"{name} needs {len(THRESHOLD_STEPS)} values, one per threshold step"
        raise ValueError(msg)


@dataclass(frozen=True)
class SectionsByStep:
    """The section a card stands in at each threshold step. Its hash is kept: the screens
    count a book's cards by it, and each of its sections hashes in Python."""

    sections: tuple[CandidateSection, ...]
    _hash: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_length(self.sections, type(self).__name__)
        object.__setattr__(self, "_hash", hash(self.sections))

    def __hash__(self) -> int:
        return self._hash

    def at(self, step: float | None) -> CandidateSection:
        return self.sections[step_index(step)]


@dataclass(frozen=True)
class NewCountsByStep:
    """How many words of a card's phrase besides the target are new at each threshold step."""

    counts: tuple[int, ...]

    def __post_init__(self) -> None:
        _check_length(self.counts, type(self).__name__)
        if any(count < 0 for count in self.counts):
            msg = f"{type(self).__name__} counts words: none may be negative"
            raise ValueError(msg)

    def at(self, step: float | None) -> int:
        return self.counts[step_index(step)]
