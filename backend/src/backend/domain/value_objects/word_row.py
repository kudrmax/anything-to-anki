from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.built_analysis import WordKey

if TYPE_CHECKING:
    from backend.domain.value_objects.built_analysis import WordData
    from backend.domain.value_objects.word_status import WordStatus


@dataclass(frozen=True)
class WordRow:
    """A light view of a word of a source: what rebuilding it needs."""

    id: int
    lemma: str
    is_phrasal_verb: bool
    status: WordStatus
    data: WordData

    @property
    def key(self) -> WordKey:
        return WordKey.of(self.lemma, self.is_phrasal_verb)

    @property
    def pos(self) -> str:
        return self.data.pos

    @property
    def zipf_frequency(self) -> float:
        return self.data.zipf_frequency
