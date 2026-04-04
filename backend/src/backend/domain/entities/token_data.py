from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenData:
    """NLP-agnostic representation of a text token.

    Abstracts spaCy Token into a pure domain object
    so that domain services can work without NLP library dependency.
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
