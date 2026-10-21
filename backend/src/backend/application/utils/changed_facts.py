"""What the changes of one write touch, collected before anything is computed, so each card
is computed once however many changes reach it."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.domain.value_objects.card_change import (
    BindingChanged,
    CardContentChanged,
    DecisionChanged,
    LevelChanged,
    MarkChanged,
    PhraseChanged,
    SourceDeleted,
    WordContentChanged,
    WordsChanged,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.value_objects.card_change import CardChange


@dataclass
class ChangedFacts:
    """`lemmas`: what the user knows of them changed, in every source (lower-case).
    `phrases`: phrases to read anew. `source_words`: source id → lemmas whose words there
    changed. `deleted_sources`: sources whose words went. `content_phrases`,
    `content_words`: cards whose content changed, not their state. `knowledge`: the
    lemmas whose knowledge changed (a decision, a mark, a binding, a timer): every card of
    one shows it, whether its stored state changes or not."""

    lemmas: set[str] = field(default_factory=set)
    knowledge: set[str] = field(default_factory=set)
    phrases: set[int] = field(default_factory=set)
    source_words: dict[int, set[str]] = field(default_factory=dict)
    deleted_sources: set[int] = field(default_factory=set)
    content_phrases: set[int] = field(default_factory=set)
    content_words: set[int] = field(default_factory=set)
    level_changed: bool = False

    @staticmethod
    def of(changes: Iterable[CardChange]) -> ChangedFacts:
        facts = ChangedFacts()
        for change in changes:
            facts._add(change)
        return facts

    def _add(self, change: CardChange) -> None:
        match change:
            case MarkChanged(lemma) | DecisionChanged(lemma) | BindingChanged(lemma):
                self.lemmas.add(lemma)
                self.knowledge.add(lemma)
            case PhraseChanged(phrase_id):
                self.phrases.add(phrase_id)
            case WordsChanged(source_id, lemmas):
                self.lemmas |= lemmas
                self.source_words.setdefault(source_id, set()).update(lemmas)
            case SourceDeleted(source_id, lemmas):
                self.lemmas |= lemmas
                self.deleted_sources.add(source_id)
            case CardContentChanged(phrase_id):
                self.content_phrases.add(phrase_id)
            case WordContentChanged(word_id):
                self.content_words.add(word_id)
            case LevelChanged():
                self.level_changed = True
