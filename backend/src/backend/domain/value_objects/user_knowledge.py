from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from backend.domain.value_objects.frequent_word_threshold import is_frequent

if TYPE_CHECKING:
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.phrase import Word
    from backend.domain.value_objects.vocabulary import Vocabulary


class NewnessFacts(Protocol):
    """What tells a word's newness: a word of a phrase, or its stored copy."""

    @property
    def lemma(self) -> str: ...

    @property
    def content(self) -> bool: ...

    @property
    def level(self) -> CEFRLevel: ...


class Newness(StrEnum):
    """When a word is new to the user, whatever the frequent word threshold."""

    ALWAYS = "always"
    IF_RARE = "if_rare"
    NEVER = "never"


def newness(word: NewnessFacts, vocabulary: Vocabulary, user_level: CEFRLevel) -> Newness:
    """Always new if the user said they don't know it or is learning it; new unless frequent
    if it is a content word above the user's level they did not say they know; else never."""
    if vocabulary.is_unknown(word.lemma) or vocabulary.is_learning(word.lemma):
        return Newness.ALWAYS
    if not word.content or vocabulary.is_known(word.lemma):
        return Newness.NEVER
    return Newness.IF_RARE if word.level.is_above(user_level) else Newness.NEVER


def is_new_at(word_newness: Newness, zipf: float, frequent_zipf: float | None) -> bool:
    """A word of this newness and frequency is new at the threshold `frequent_zipf`."""
    if word_newness is Newness.IF_RARE:
        return not is_frequent(zipf, frequent_zipf)
    return word_newness is Newness.ALWAYS


class NewnessRule(Protocol):
    """What tells the newness of a word."""

    def newness(self, word: NewnessFacts) -> Newness: ...


class RememberedNewness:
    """`KnowledgeBase.newness`, each kind of word (lemma, content, level) worked out once: a
    book's phrases hold a million words of a few thousand kinds."""

    def __init__(self, base: KnowledgeBase) -> None:
        self._base = base
        self._found: dict[tuple[str, bool, CEFRLevel], Newness] = {}

    def newness(self, word: NewnessFacts) -> Newness:
        key = (word.lemma, word.content, word.level)
        found = self._found.get(key)
        if found is None:
            found = self._found[key] = self._base.newness(word)
        return found


@dataclass(frozen=True)
class KnowledgeBase:
    """What the user knows apart from the frequent word threshold."""

    vocabulary: Vocabulary
    user_level: CEFRLevel

    def newness(self, word: NewnessFacts) -> Newness:
        return newness(word, self.vocabulary, self.user_level)


@dataclass(frozen=True)
class UserKnowledge:
    """What decides whether a word is new to the user, right now.

    `frequent_zipf`: words at least this frequent count as known; None — frequency is ignored.
    """

    vocabulary: Vocabulary
    user_level: CEFRLevel
    frequent_zipf: float | None

    @property
    def base(self) -> KnowledgeBase:
        return KnowledgeBase(self.vocabulary, self.user_level)

    def is_new(self, word: Word) -> bool:
        """New if the user said they don't know it or is learning it, or it is a content word
        above the user's level, not frequent, and not one they said they know."""
        word_newness = newness(word, self.vocabulary, self.user_level)
        return is_new_at(word_newness, word.zipf, self.frequent_zipf)
