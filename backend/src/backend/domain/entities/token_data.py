from __future__ import annotations

import sys
from dataclasses import dataclass

# Strings repeated across tokens: a book holds millions of tokens over a few thousand words.
SHARED_STRINGS = ("text", "lemma", "pos", "tag", "dep", "whitespace_after")


@dataclass(frozen=True, slots=True)
class TokenData:
    """NLP-agnostic representation of a text token.

    Abstracts spaCy Token into a pure domain object
    so that domain services can work without NLP library dependency.
    A book is millions of tokens, so a token keeps no dict and shares its strings with
    every other token that has them.
    """

    index: int
    text: str
    lemma: str
    pos: str  # Universal POS tag (NOUN, VERB, ADJ, ...)
    tag: str  # Penn Treebank tag (NN, VB, JJ, ...) — used by cefrpy
    head_index: int
    children_indices: tuple[int, ...]
    is_punct: bool
    is_stop: bool
    is_alpha: bool
    is_propn: bool
    sent_index: int
    dep: str = ""  # Dependency relation label (e.g. "prt", "prep", "ROOT")
    whitespace_after: str = ""  # Trailing whitespace as it appears in original text
    char_start: int = 0  # Offset of the token in the analysed text

    def __post_init__(self) -> None:
        for field in SHARED_STRINGS:
            object.__setattr__(self, field, sys.intern(getattr(self, field)))

    @property
    def char_end(self) -> int:
        return self.char_start + len(self.text)
