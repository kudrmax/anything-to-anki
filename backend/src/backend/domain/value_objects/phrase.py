from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.value_objects.cefr_level import CEFRLevel

TARGET_SEPARATOR = " "


@dataclass(frozen=True, slots=True)
class Word:
    """A word of a phrase: characters [start, end) of its text and what is known of it.

    `content`: a word that can be new to the user — not a function word, not a name.
    A book's phrases hold millions of words, so a word keeps no dict and shares its lemma
    with every other word that has it.
    """

    start: int
    end: int
    lemma: str
    level: CEFRLevel
    zipf: float
    content: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemma", sys.intern(self.lemma))


@dataclass(frozen=True)
class Phrase:
    """A card's phrase: the text as it is, its words by characters, the target by word numbers.

    Punctuation, quotes and line breaks stay in the text and are not words.
    """

    text: str
    words: tuple[Word, ...]
    target: tuple[int, ...]

    def __post_init__(self) -> None:
        previous_end = 0
        for word in self.words:
            if not 0 <= word.start < word.end <= len(self.text):
                raise ValueError(f"Word {word.start}..{word.end} is outside the text")
            if word.start < previous_end:
                raise ValueError("Words must go in order without overlapping")
            previous_end = word.end
        if not self.target:
            raise ValueError("A phrase needs a target")
        if any(not 0 <= index < len(self.words) for index in self.target):
            raise ValueError("The target points past the words")
        if list(self.target) != sorted(set(self.target)):
            raise ValueError("The target words must go in order, once each")

    def word_text(self, index: int) -> str:
        word = self.words[index]
        return self.text[word.start:word.end]

    def target_text(self) -> str:
        """The target as written in the phrase: "gave up" for "gave it up"."""
        return TARGET_SEPARATOR.join(self.word_text(i) for i in self.target)

    def other_words(self) -> tuple[Word, ...]:
        target = set(self.target)
        return tuple(word for i, word in enumerate(self.words) if i not in target)

    def runs(self, indices: Iterable[int]) -> list[tuple[int, int]]:
        """Characters [start, end) of the given words; words with consecutive numbers make one
        run, with whatever stands between them."""
        runs: list[tuple[int, int]] = []
        previous: int | None = None
        for i in sorted(i for i in set(indices) if 0 <= i < len(self.words)):
            word = self.words[i]
            if previous is not None and i == previous + 1:
                runs[-1] = (runs[-1][0], word.end)
            else:
                runs.append((word.start, word.end))
            previous = i
        return runs

    def with_target(self, target: tuple[int, ...]) -> Phrase:
        return replace(self, target=target)
