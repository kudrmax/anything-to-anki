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
    """What the card of a phrase shows changed, not its state: its generated content
    (meaning, simplification, media) or its phrase's text or place in the source."""

    phrase_id: int


@dataclass(frozen=True)
class WordContentChanged:
    """What every card of a word shows changed, not its state: the word's generated
    content (translation, synonyms) or its data (level, frequency)."""

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
