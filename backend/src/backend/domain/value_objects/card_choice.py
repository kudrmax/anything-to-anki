"""One status model: a card's choice, its binding to an Anki note, and the word's status."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.value_objects.learning_timer import timer_due
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge


class CardChoice(StrEnum):
    """The one button chosen on a card, or none."""

    NONE = "none"
    LEARN = "learn"
    CLOZE = "cloze"
    KNOWN = "known"
    SKIP = "skip"


class NoteKind(StrEnum):
    LEARN = "learn"
    CLOZE = "cloze"


class DecisionStatus(StrEnum):
    """The word's status as stored: no time in it."""

    NEW = "pending"
    LEARN = "learn"
    LEARNING = "learning"
    KNOWN = "known"


class Press(StrEnum):
    LEARN = "learn"
    CLOZE = "cloze"
    KNOWN = "known"
    SKIP = "skip"


class Role(StrEnum):
    """DECISION: the word's decision card. OTHER: the decision is on another card. OPEN: the
    word has no decision."""

    DECISION = "decision"
    OTHER = "other"
    OPEN = "open"


class Refusal(StrEnum):
    NOT_DECISION_CARD = "not_decision_card"
    DECIDED_ELSEWHERE = "decided_elsewhere"


class Actor(StrEnum):
    USER = "user"
    EXPORT = "export"
    REVOKE = "revoke"


DECISION_CHOICES: frozenset[CardChoice] = frozenset(
    {CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN},
)
CHOICE_OF_KIND: Mapping[NoteKind, CardChoice] = MappingProxyType(
    {NoteKind.LEARN: CardChoice.LEARN, NoteKind.CLOZE: CardChoice.CLOZE},
)
KIND_OF_CHOICE: Mapping[CardChoice, NoteKind] = MappingProxyType(
    {choice: kind for kind, choice in CHOICE_OF_KIND.items()},
)
PRESS_OF_KIND: Mapping[NoteKind, Press] = MappingProxyType(
    {NoteKind.LEARN: Press.LEARN, NoteKind.CLOZE: Press.CLOZE},
)
OTHER_KIND: Mapping[NoteKind, NoteKind] = MappingProxyType(
    {NoteKind.LEARN: NoteKind.CLOZE, NoteKind.CLOZE: NoteKind.LEARN},
)
CHOICE_OF_PRESS: Mapping[Press, CardChoice] = MappingProxyType(
    {
        Press.LEARN: CardChoice.LEARN, Press.CLOZE: CardChoice.CLOZE,
        Press.KNOWN: CardChoice.KNOWN, Press.SKIP: CardChoice.SKIP,
    },
)


@dataclass(frozen=True)
class Binding:
    """The card's active binding to an Anki note; its timer starts at that export."""

    note_kind: NoteKind
    learning_since: datetime


@dataclass(frozen=True)
class CardState:
    card_id: int
    choice: CardChoice
    binding: Binding | None = None

    @property
    def is_decision(self) -> bool:
        return self.choice in DECISION_CHOICES

    @property
    def note(self) -> NoteKind | None:
        return None if self.binding is None else self.binding.note_kind


_NO_DECISION_CARD = CardState(card_id=0, choice=CardChoice.NONE)


@dataclass(frozen=True)
class WordState:
    word_id: int
    lemma: str
    pos: str
    source_id: int
    cards: tuple[CardState, ...]

    def card(self, card_id: int) -> CardState:
        found = next((card for card in self.cards if card.card_id == card_id), None)
        if found is None:
            raise PhraseNotFoundError(card_id)
        return found

    @property
    def decision_card(self) -> CardState | None:
        return next((card for card in self.cards if card.is_decision), None)

    @property
    def decision_choice(self) -> CardChoice:
        """The decision card's choice; NONE when the word has no decision."""
        return _decision(self).choice

    @property
    def decision_note(self) -> NoteKind | None:
        return _decision(self).note

    def with_cards(self, *changed: CardState) -> WordState:
        """Replaces cards by id in place; cards with a new id are appended."""
        by_id = {card.card_id: card for card in changed}
        kept = tuple(by_id.get(card.card_id, card) for card in self.cards)
        known_ids = {card.card_id for card in self.cards}
        added = tuple(card for card in changed if card.card_id not in known_ids)
        return replace(self, cards=kept + added)


_DECISION_STATUS: Mapping[tuple[CardChoice, bool], DecisionStatus] = MappingProxyType(
    {
        (CardChoice.NONE, False): DecisionStatus.NEW,
        (CardChoice.LEARN, False): DecisionStatus.LEARN,
        (CardChoice.CLOZE, False): DecisionStatus.LEARN,
        (CardChoice.LEARN, True): DecisionStatus.LEARNING,
        (CardChoice.CLOZE, True): DecisionStatus.LEARNING,
        (CardChoice.KNOWN, False): DecisionStatus.KNOWN,
        (CardChoice.KNOWN, True): DecisionStatus.KNOWN,
    },
)
_STATUS_OF: Mapping[tuple[DecisionStatus, bool], WordStatus] = MappingProxyType(
    {
        (DecisionStatus.NEW, False): WordStatus.NEW,
        (DecisionStatus.LEARN, False): WordStatus.LEARN,
        (DecisionStatus.LEARN, True): WordStatus.KNOWN,
        (DecisionStatus.LEARNING, False): WordStatus.LEARNING,
        (DecisionStatus.LEARNING, True): WordStatus.KNOWN,
        (DecisionStatus.KNOWN, False): WordStatus.KNOWN,
    },
)


def in_anki(card: CardState) -> bool:
    """The only "in Anki" predicate."""
    return card.binding is not None


def is_skipped(card: CardState) -> bool:
    return card.choice is CardChoice.SKIP


def export_kind(card: CardState) -> NoteKind | None:
    return KIND_OF_CHOICE.get(card.choice)


def is_cloze(card: CardState) -> bool:
    """The card goes to Anki as a cloze note."""
    return export_kind(card) is NoteKind.CLOZE


def decision_status(word: WordState) -> DecisionStatus:
    card = _decision(word)
    return _DECISION_STATUS[(card.choice, in_anki(card))]


def reads_known(card: CardState, lemma: LemmaKnowledge, now: datetime) -> bool:
    """A Learn or Cloze card reads Known by the list, or, in Anki, by the timer of its own
    binding. The list counts on a card not exported yet too: the later action wins (Q15)."""
    kind = export_kind(card)
    binding = card.binding
    return (
        kind is not None
        and (binding is None or binding.note_kind is kind)
        and (
            lemma.listed_known
            or (binding is not None and timer_due(binding.learning_since, now))
        )
    )


def status_of(word: WordState, lemma: LemmaKnowledge, now: datetime) -> WordStatus:
    """What every reader sees: the decision, with Learn or Learning read as Known when it
    reads so."""
    return _STATUS_OF[(decision_status(word), decision_reads_known(word, lemma, now))]


def chosen_status(word: WordState) -> WordStatus:
    """The status the decision itself says, without the lists or timers: what a word is
    right after the user decides on it, since the user's latest action wins. No press
    leaves a Learn or Cloze card bound, so a timer never matters here."""
    return _CHOSEN_STATUS[decision_status(word)]


_CHOSEN_STATUS: Mapping[DecisionStatus, WordStatus] = MappingProxyType(
    {status: WordStatus(status.value) for status in DecisionStatus},
)


def decision_reads_known(word: WordState, lemma: LemmaKnowledge, now: datetime) -> bool:
    return reads_known(_decision(word), lemma, now)


def _decision(word: WordState) -> CardState:
    """The decision card, or a private placeholder so "no decision" is a key value."""
    return next((card for card in word.cards if card.is_decision), _NO_DECISION_CARD)


def studied_at(word: WordState, now: datetime) -> datetime | None:
    """When the word was last marked, right after a press at `now`: none once the press
    left no card of it marked."""
    return now if any(card.choice is not CardChoice.NONE for card in word.cards) else None
