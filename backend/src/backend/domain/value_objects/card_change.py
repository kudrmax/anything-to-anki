from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionChanged:
    """The user's Learn/Known decision on a lemma changed."""

    lemma: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemma", self.lemma.lower())


@dataclass(frozen=True)
class PhraseChanged:
    """A phrase appeared, went away or changed its text, its source or its targets."""

    phrase_id: int


@dataclass(frozen=True)
class WordsChanged:
    """The words of a source's phrases changed; `lemmas` are the ones affected."""

    source_id: int
    lemmas: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemmas", frozenset(lemma.lower() for lemma in self.lemmas))


@dataclass(frozen=True)
class SourceDeleted:
    """A source was deleted; `lemmas` are the ones its phrases carried."""

    source_id: int
    lemmas: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemmas", frozenset(lemma.lower() for lemma in self.lemmas))


@dataclass(frozen=True)
class MarkChanged:
    """A user mark (such as skipped or flagged) on a lemma's cards changed."""

    lemma: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemma", self.lemma.lower())


@dataclass(frozen=True)
class BindingChanged:
    """The Anki binding of a lemma's card was created, ended or changed."""

    lemma: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "lemma", self.lemma.lower())


@dataclass(frozen=True)
class CardContentChanged:
    """The generated card content of a phrase (meaning, simplification, media) changed."""

    phrase_id: int


@dataclass(frozen=True)
class WordContentChanged:
    """The generated content of a word (translation, synonyms) changed."""

    word_id: int


@dataclass(frozen=True)
class LevelChanged:
    """The user's language level changed, which moves every card's difficulty."""


CardChange = (
    DecisionChanged
    | PhraseChanged
    | WordsChanged
    | SourceDeleted
    | MarkChanged
    | BindingChanged
    | CardContentChanged
    | WordContentChanged
    | LevelChanged
)
