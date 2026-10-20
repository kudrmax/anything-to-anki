"""Rows of the stored projection of card state (spec §5): what the review reads of every
shown card, word and other word of a phrase, derived from the facts by the domain rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
    from backend.domain.value_objects.card_choice import DecisionStatus
    from backend.domain.value_objects.cefr_level import CEFRLevel
    from backend.domain.value_objects.user_knowledge import Newness


@dataclass(frozen=True)
class CardStateRow:
    """A shown phrase of a word. `lemma` is lower-case. `changes_at`: the first moment the
    card's state changes by itself (its lemma's Anki timer), None when nothing is due."""

    phrase_id: int
    source_id: int
    word_id: int
    lemma: str
    is_done: bool
    wants_generation: bool
    sections: SectionsByStep
    new_counts: NewCountsByStep
    changes_at: datetime | None


@dataclass(frozen=True)
class WordStateRow:
    """A word of a source with its decision status. `lemma` is lower-case."""

    word_id: int
    source_id: int
    lemma: str
    status: DecisionStatus


@dataclass(frozen=True)
class PhraseWordRow:
    """A word of a shown phrase besides its target. `position`: its number among the
    phrase's words; `lemma` is lower-case."""

    lemma: str
    phrase_id: int
    position: int
    zipf: float
    content: bool
    level: CEFRLevel
    newness: Newness


@dataclass(frozen=True)
class CardStates:
    """Every row of the projection, as computed at one moment."""

    cards: tuple[CardStateRow, ...]
    words: tuple[WordStateRow, ...]
    phrase_words: tuple[PhraseWordRow, ...]


@dataclass(frozen=True)
class StoredCardState:
    """A stored card row: `revision` is the projection revision that last wrote it;
    `removed` marks a card gone since."""

    row: CardStateRow
    revision: int
    removed: bool


@dataclass(frozen=True)
class StoredCardStates:
    """Every stored row of the projection and the projection's current revision."""

    cards: tuple[StoredCardState, ...]
    words: tuple[WordStateRow, ...]
    phrase_words: tuple[PhraseWordRow, ...]
    revision: int
