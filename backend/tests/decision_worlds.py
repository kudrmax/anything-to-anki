"""Generated worlds for the decision-table tests: a word with the acted card and maybe a
sibling, other sources of the lemma, orphaned bindings, and the lemma's lists."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from functools import cache

from backend.domain.services.decision_rules import BindingRef
from backend.domain.value_objects.card_choice import (
    CHOICE_OF_KIND,
    Binding,
    CardChoice,
    CardState,
    DecisionStatus,
    NoteKind,
    WordState,
    decision_status,
)
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER_DAYS
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)
DUE = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS)
FRESH = NOW - timedelta(days=LEARNING_KNOWN_AFTER_DAYS - 1)
LEMMA = "procrastinate"
ACTED = 1
SIBLING = 2
NEW_CARD = 99
N, L, C, K, S = (
    CardChoice.NONE, CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP,
)


def single(word_id: int, choice: CardChoice, binding: Binding | None = None) -> WordState:
    return WordState(word_id, LEMMA, "verb", word_id, (CardState(word_id * 10, choice, binding),))


BINDINGS = (None, *(Binding(kind, since) for kind in NoteKind for since in (FRESH, DUE)))
SIBLINGS = (
    None,
    *(CardState(SIBLING, choice, binding) for choice in CardChoice for binding in BINDINGS),
)
OTHER_SOURCES: tuple[tuple[WordState, ...], ...] = (
    (),
    (single(2, K),),
    (single(3, L),),
    (single(4, L, Binding(NoteKind.LEARN, FRESH)),),
    (single(5, C, Binding(NoteKind.CLOZE, DUE)),),
    (single(6, K, Binding(NoteKind.LEARN, DUE)), single(7, S)),
)
ORPHANS: tuple[tuple[BindingRef, ...], ...] = (
    (), (BindingRef(501, DUE),), (BindingRef(502, FRESH),),
)


@dataclass(frozen=True)
class World:
    word: WordState
    others: tuple[WordState, ...]
    orphans: tuple[BindingRef, ...]
    known_marked: bool
    unknown: bool

    @property
    def words(self) -> tuple[WordState, ...]:
        return (self.word, *self.others)

    def knowledge(self) -> LemmaKnowledge:
        since = tuple(
            card.binding.learning_since
            for word in self.words for card in word.cards if card.binding is not None
        ) + tuple(ref.learning_since for ref in self.orphans)
        return LemmaKnowledge.at(
            NOW, known_marked=self.known_marked, unknown=self.unknown,
            learn_anywhere=any(decision_status(w) is DecisionStatus.LEARN for w in self.words),
            active_since=since,
        )

    def elsewhere(self) -> ElsewhereStatus | None:
        knowledge = self.knowledge()
        if knowledge.is_known:
            return ElsewhereStatus.KNOWN
        if knowledge.is_learning:
            return ElsewhereStatus.LEARNING
        if knowledge.is_learn:
            return ElsewhereStatus.LEARN
        return None

    def replacing(self, *words: WordState) -> World:
        by_id = {w.word_id: w for w in words}
        return replace(
            self, word=by_id.get(self.word.word_id, self.word),
            others=tuple(by_id.get(w.word_id, w) for w in self.others),
        )


def well_formed(word: WordState) -> bool:
    """One decision card at most; A1 and A2."""
    decisions = [card for card in word.cards if card.is_decision]
    bound = [card for card in word.cards if card.binding is not None]
    return len(decisions) <= 1 and all(_a1(card) for card in bound)


def _a1(card: CardState) -> bool:
    assert card.binding is not None
    return card.is_decision and card.choice in {CHOICE_OF_KIND[card.binding.note_kind], K}


def holds_ak(world: World) -> bool:
    known_cards = [
        card for word in world.words for card in word.cards if card.choice is K
    ]
    return world.known_marked or not known_cards


def _valid(world: World) -> bool:
    known_choice = any(card.choice is K for word in world.words for card in word.cards)
    return (
        all(well_formed(word) for word in world.words)
        and holds_ak(world)
        and not (world.unknown and (world.known_marked or known_choice))
    )


@cache
def worlds() -> tuple[World, ...]:
    built = []
    for choice, binding, sibling, others, orphans, known_marked, unknown in itertools.product(
        CardChoice, BINDINGS, SIBLINGS, OTHER_SOURCES, ORPHANS, (False, True), (False, True),
    ):
        cards = (CardState(ACTED, choice, binding), *(() if sibling is None else (sibling,)))
        world = World(
            WordState(1, LEMMA, "verb", 1, cards), others, orphans, known_marked, unknown,
        )
        if _valid(world):
            built.append(world)
    return tuple(built)
