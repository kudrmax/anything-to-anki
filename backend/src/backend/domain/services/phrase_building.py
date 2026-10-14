"""Turning a text and what a parser found in it into a Phrase."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Phrase, Word

if TYPE_CHECKING:
    from collections.abc import Sequence

# A word: letters and digits, with apostrophes and hyphens inside ("don't", "well-known").
_WORD = re.compile(r"(?:[^\W_]|['’-])+")
_EDGE = "'’-"
_LEMMA_SEPARATOR = " "
_HYPHEN = "-"


@dataclass(frozen=True)
class TokenFacts:
    """What the parser and the dictionaries say about one token, placed in the text."""

    start: int
    end: int
    lemma: str
    level: CEFRLevel
    zipf: float
    content: bool
    alpha: bool


def word_spans(text: str) -> list[tuple[int, int]]:
    """The words of a text by characters; punctuation and spaces are not words."""
    spans: list[tuple[int, int]] = []
    for match in _WORD.finditer(text):
        start, end = match.start(), match.end()
        while start < end and text[start] in _EDGE:
            start += 1
        while end > start and text[end - 1] in _EDGE:
            end -= 1
        if start < end:
            spans.append((start, end))
    return spans


def words_of(text: str, tokens: Sequence[TokenFacts]) -> tuple[Word, ...]:
    """Each word takes the facts of the one token it is; a word of several tokens
    ("don't") is its own lowercase text, with no level."""
    words: list[Word] = []
    for start, end in word_spans(text):
        inside = [t for t in tokens if t.start < end and start < t.end]
        alpha = [t for t in inside if t.alpha]
        if len(inside) == 1 and alpha:
            only = alpha[0]
            words.append(Word(start, end, only.lemma.lower(), only.level, only.zipf, only.content))
        else:
            words.append(Word(
                start, end, text[start:end].lower(), CEFRLevel.UNKNOWN,
                max((t.zipf for t in inside), default=0.0),
                any(t.content for t in inside),
            ))
    return tuple(words)


def build_phrase(
    text: str, tokens: Sequence[TokenFacts], target_spans: Sequence[tuple[int, int]],
) -> Phrase:
    """The phrase whose target is the words the given characters touch."""
    words = words_of(text, tokens)
    target = tuple(
        i for i, word in enumerate(words)
        if any(word.start < end and start < word.end for start, end in target_spans)
    )
    if not target:
        raise TargetNotInPhraseError()
    return Phrase(text=text, words=words, target=target)


def target_by_lemma(words: Sequence[Word], text: str, lemma: str) -> tuple[int, ...]:
    """The first place the target stands in the words, by dictionary form, as written or
    as a part of a hyphenated word: "give up" finds "gave … up", "dong" finds "ding-dong";
    its parts in another order only when not in order. Nothing when it is not there."""
    wanted = lemma.lower().split(_LEMMA_SEPARATOR)

    def matches(index: int, part: str) -> bool:
        word = words[index]
        written = text[word.start:word.end].lower()
        return part in (word.lemma, written) or part in written.split(_HYPHEN)

    for first in range(len(words)):
        if not matches(first, wanted[0]):
            continue
        found = [first]
        for part in wanted[1:]:
            following = next(
                (i for i in range(found[-1] + 1, len(words)) if matches(i, part)), None,
            )
            if following is None:
                break
            found.append(following)
        if len(found) == len(wanted):
            return tuple(found)
    # A particle may stand before its verb: "in which well-being is built" for "build in".
    anywhere: list[int] = []
    for part in wanted:
        index = next(
            (i for i in range(len(words)) if i not in anywhere and matches(i, part)), None,
        )
        if index is None:
            return ()
        anywhere.append(index)
    return tuple(sorted(anywhere))
