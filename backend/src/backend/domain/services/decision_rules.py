"""The decision tables: what a press, a move, an export and a Known removal do to a word.

Every condition is in a rule key, and every possible key has exactly one row. Effects are a
function of the status change; a row adds only its own card effects (RELEASE, and MARK_KNOWN
on M3k when the lemma was Known only by its timer).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.exceptions import ActionRefusedError, NoDecisionRuleError
from backend.domain.value_objects.card_choice import (
    CHOICE_OF_KIND,
    CHOICE_OF_PRESS,
    DECISION_CHOICES,
    KIND_OF_CHOICE,
    OTHER_KIND,
    PRESS_OF_KIND,
    Actor,
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    Press,
    Refusal,
    Role,
    WordState,
    reads_known,
    status_of,
)
from backend.domain.value_objects.learning_timer import timer_due
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from datetime import datetime

    from backend.domain.value_objects.elsewhere import ElsewhereStatus
    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge


class Effect(StrEnum):
    MARK_KNOWN = "mark_known"
    REMOVE_KNOWN = "remove_known"
    CALIBRATE = "calibrate"
    FORGET_CALIBRATION = "forget_calibration"
    BIND = "bind"
    RELEASE = "release"
    REFRESH_SOURCE = "refresh_source"
    REFRESH_LEMMA = "refresh_lemma"


_NO_EFFECTS: frozenset[Effect] = frozenset()
_RELEASED: frozenset[Effect] = frozenset({Effect.RELEASE})

_N, _L, _C, _K, _S = (
    CardChoice.NONE, CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP,
)


def rule[K, V](table: Mapping[K, V], key: K) -> V:
    try:
        return table[key]
    except KeyError:
        raise NoDecisionRuleError(key) from None


def role_of(word: WordState, card: CardState) -> Role:
    return _ROLES[(card.is_decision, word.decision.is_decision)]


_ROLES: Mapping[tuple[bool, bool], Role] = MappingProxyType(
    {(True, True): Role.DECISION, (False, True): Role.OTHER, (False, False): Role.OPEN},
)


def _holds_binding(note: NoteKind | None, choice: CardChoice | None) -> bool:
    """A1: an active binding sits on a decision card whose choice is its kind or KNOWN."""
    return note is None or choice in {CHOICE_OF_KIND[note], _K}


def _learning(note: NoteKind | None, choice: CardChoice | None) -> bool:
    return note is not None and choice is CHOICE_OF_KIND[note]


def _kept(binding: Binding | None, release: bool) -> Binding | None:
    return None if release else binding


_RELEASE_EFFECTS: Mapping[bool, frozenset[Effect]] = MappingProxyType(
    {True: _RELEASED, False: _NO_EFFECTS},
)


# --- outcomes ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatusChange:
    word_id: int
    before: WordStatus
    after: WordStatus
    actor: Actor


@dataclass(frozen=True)
class ChoiceChange:
    card_id: int
    before: CardChoice
    after: CardChoice


@dataclass(frozen=True)
class WordOutcome:
    """The word after a row, and what must follow. `status` is always set; before equals
    after when only a choice changed."""

    row: str
    word: WordState
    choices: tuple[ChoiceChange, ...]
    released: bool
    status: StatusChange
    row_effects: frozenset[Effect] = _NO_EFFECTS

    @property
    def effects(self) -> frozenset[Effect]:
        return effects(self.status) | self.row_effects


@dataclass(frozen=True)
class BindingRef:
    """An active binding whose card or source is gone."""

    binding_id: int
    learning_since: datetime


@dataclass(frozen=True)
class KnownRemoval:
    words: tuple[WordOutcome, ...]
    released_orphans: tuple[int, ...]


def _change(
    before: WordState, after: WordState, lemma: LemmaKnowledge, now: datetime, actor: Actor,
) -> StatusChange:
    return StatusChange(
        before.word_id, status_of(before, lemma, now), status_of(after, lemma, now), actor,
    )


# --- press (§2.4) -------------------------------------------------------------------------


@dataclass(frozen=True)
class PressKey:
    role: Role
    note: NoteKind | None
    reads_known: bool
    elsewhere: bool
    before: CardChoice
    press: Press


@dataclass(frozen=True)
class Target:
    """The card's new choice and whether its binding is released; a refusal row sets
    `refusal`, and its `choice` is never applied."""

    row: str
    choice: CardChoice = CardChoice.NONE
    release: bool = False
    refusal: Refusal | None = None


@dataclass(frozen=True)
class PressRow:
    role: Role
    note: NoteKind | None
    reads_known: bool
    elsewhere: bool
    before: frozenset[CardChoice]
    press: frozenset[Press]
    target: Target


def expand(row: PressRow) -> tuple[PressKey, ...]:
    return tuple(
        PressKey(row.role, row.note, row.reads_known, row.elsewhere, before, button)
        for before, button in product(row.before, row.press)
    )


def possible(key: PressKey) -> bool:
    """Keys that A1, A2 and the normalisation of reads_known and elsewhere allow."""
    return (
        (key.before in DECISION_CHOICES) is (key.role is Role.DECISION)
        and _holds_binding(key.note, key.before)
        and (not key.reads_known or _learning(key.note, key.before))
        and (not key.elsewhere or key.role is Role.OPEN)
    )


_DECIDING = frozenset({Press.LEARN, Press.CLOZE, Press.KNOWN})

_KIND_PRESSES = (Press.LEARN, Press.CLOZE)


def _open(
    row: str, elsewhere: bool, before: Iterable[CardChoice], presses: Iterable[Press],
    choice: CardChoice = _N, *, refusal: Refusal | None = None,
) -> PressRow:
    return PressRow(
        Role.OPEN, None, False, elsewhere, frozenset(before), frozenset(presses),
        Target(row, choice, refusal=refusal),
    )


def _decided(
    row: str, before: Iterable[CardChoice], presses: Iterable[Press], choice: CardChoice,
) -> PressRow:
    return PressRow(
        Role.DECISION, None, False, False, frozenset(before), frozenset(presses),
        Target(row, choice),
    )


def _bound(
    row: str, kind: NoteKind, reads: bool, before: Iterable[CardChoice],
    presses: Iterable[Press], choice: CardChoice, *, release: bool = True,
) -> PressRow:
    return PressRow(
        Role.DECISION, kind, reads, False, frozenset(before), frozenset(presses),
        Target(row, choice, release),
    )


def _other(
    row: str, before: Iterable[CardChoice], presses: Iterable[Press],
    choice: CardChoice = _N, *, refusal: Refusal | None = None,
) -> PressRow:
    return PressRow(
        Role.OTHER, None, False, False, frozenset(before), frozenset(presses),
        Target(row, choice, refusal=refusal),
    )


def _unbound_kind_rows(kind: NoteKind) -> tuple[PressRow, ...]:
    choice, other = CHOICE_OF_KIND[kind], OTHER_KIND[kind]
    return (
        _decided("P9", {choice}, {PRESS_OF_KIND[kind]}, _N),
        _decided("P10", {choice}, {PRESS_OF_KIND[other]}, CHOICE_OF_KIND[other]),
    )


def _bound_kind_rows(kind: NoteKind) -> tuple[PressRow, ...]:
    choice, other = CHOICE_OF_KIND[kind], OTHER_KIND[kind]
    return (
        _bound("P16", kind, False, {choice}, {Press.KNOWN}, _K, release=False),
        _bound("P17", kind, False, {choice}, {PRESS_OF_KIND[kind]}, _N),
        _bound("P18", kind, False, {choice}, {PRESS_OF_KIND[other]}, CHOICE_OF_KIND[other]),
        _bound("P19", kind, False, {choice}, {Press.SKIP}, _S),
        _bound("P20", kind, False, {_K}, {Press.KNOWN}, _N),
        _bound("P21", kind, False, {_K}, {Press.SKIP}, _S),
        *(_bound("P22", kind, False, {_K}, {p}, CHOICE_OF_PRESS[p]) for p in _KIND_PRESSES),
        _bound("P23", kind, True, {choice}, {Press.KNOWN}, _N),
        *(_bound("P24", kind, True, {choice}, {p}, CHOICE_OF_PRESS[p]) for p in _KIND_PRESSES),
        _bound("P24s", kind, True, {choice}, {Press.SKIP}, _S),
    )


PRESS_ROWS: tuple[PressRow, ...] = (
    _open("P1", False, {_N, _S}, {Press.LEARN}, _L),
    _open("P2", False, {_N, _S}, {Press.CLOZE}, _C),
    _open("P3", False, {_N, _S}, {Press.KNOWN}, _K),
    _open("P4", False, {_N}, {Press.SKIP}, _S),
    _open("P5", False, {_S}, {Press.SKIP}, _N),
    _open("P6", True, {_N, _S}, _DECIDING, refusal=Refusal.DECIDED_ELSEWHERE),
    _open("P7", True, {_N}, {Press.SKIP}, _S),
    _open("P8", True, {_S}, {Press.SKIP}, _N),
    *(row for kind in NoteKind for row in _unbound_kind_rows(kind)),
    _decided("P11", {_L, _C}, {Press.KNOWN}, _K),
    _decided("P12", {_L, _C}, {Press.SKIP}, _S),
    _decided("P13", {_K}, {Press.KNOWN}, _N),
    *(_decided("P14", {_K}, {p}, CHOICE_OF_PRESS[p]) for p in _KIND_PRESSES),
    _decided("P15", {_K}, {Press.SKIP}, _S),
    *(row for kind in NoteKind for row in _bound_kind_rows(kind)),
    _other("P25", {_N}, Press, refusal=Refusal.NOT_DECISION_CARD),
    _other("P26", {_S}, {Press.SKIP}, _N),
    _other("P27", {_S}, _DECIDING, refusal=Refusal.NOT_DECISION_CARD),
)
PRESS_RULES: Mapping[PressKey, Target] = MappingProxyType(
    {key: row.target for row in PRESS_ROWS for key in expand(row)},
)


def press_key(
    word: WordState, card_id: int, button: Press, lemma: LemmaKnowledge,
    elsewhere: ElsewhereStatus | None, now: datetime,
) -> PressKey:
    card = word.card(card_id)
    role = role_of(word, card)
    return PressKey(
        role=role,
        note=card.note,
        reads_known=reads_known(card, lemma, now),
        elsewhere=role is Role.OPEN and elsewhere is not None,
        before=card.choice,
        press=button,
    )


def press(
    word: WordState, card_id: int, button: Press, lemma: LemmaKnowledge,
    elsewhere: ElsewhereStatus | None, now: datetime,
) -> WordOutcome:
    """Raises ActionRefusedError when the row refuses."""
    card = word.card(card_id)
    target = rule(PRESS_RULES, press_key(word, card_id, button, lemma, elsewhere, now))
    if target.refusal is not None:
        raise ActionRefusedError(card_id, target.refusal)
    choice = target.choice
    after = word.with_cards(CardState(card_id, choice, _kept(card.binding, target.release)))
    return WordOutcome(
        row=target.row,
        word=after,
        choices=(ChoiceChange(card_id, card.choice, choice),),
        released=target.release,
        status=_change(word, after, lemma, now, Actor.USER),
        row_effects=_RELEASE_EFFECTS[target.release],
    )


# --- move: Replace with example (§2.5) ----------------------------------------------------


@dataclass(frozen=True)
class MoveKey:
    note: NoteKind | None
    reads_known: bool
    timer_only: bool       # normalised: reads Known by its timer while the lemma is not listed
    before: CardChoice


@dataclass(frozen=True)
class MoveTarget:
    row: str
    new_card: CardChoice
    old_card: CardChoice
    effects: frozenset[Effect] = _NO_EFFECTS

    @property
    def release(self) -> bool:
        return Effect.RELEASE in self.effects


def possible_move(key: MoveKey) -> bool:
    return (
        _holds_binding(key.note, key.before)
        and (not key.reads_known or _learning(key.note, key.before))
        and (not key.timer_only or key.reads_known)
    )


# M3a / M3k keep the status, but the released row changes the lemma's bindings (and the
# Settings lists) that other sources read.
_RELEASED_FOR_LEMMA: frozenset[Effect] = _RELEASED | {Effect.REFRESH_LEMMA}


def _bound_moves(kind: NoteKind) -> tuple[tuple[MoveKey, MoveTarget], ...]:
    choice = CHOICE_OF_KIND[kind]
    return (
        (MoveKey(kind, False, False, _K), MoveTarget("M3a", _K, _N, _RELEASED_FOR_LEMMA)),
        (MoveKey(kind, True, False, choice), MoveTarget("M3k", _K, _N, _RELEASED_FOR_LEMMA)),
        (
            MoveKey(kind, True, True, choice),
            MoveTarget("M3k", _K, _N, _RELEASED_FOR_LEMMA | {Effect.MARK_KNOWN}),
        ),
        (MoveKey(kind, False, False, choice), MoveTarget("M3b", choice, _N, _RELEASED)),
    )


MOVE_ROWS: tuple[tuple[MoveKey, MoveTarget], ...] = (
    *((MoveKey(None, False, False, c), MoveTarget("M1", c, _N)) for c in (_L, _C, _K)),
    *((MoveKey(None, False, False, c), MoveTarget("M2", _N, c)) for c in (_N, _S)),
    *(row for kind in NoteKind for row in _bound_moves(kind)),
)
MOVE_RULES: Mapping[MoveKey, MoveTarget] = MappingProxyType(dict(MOVE_ROWS))


def move_key(card: CardState, lemma: LemmaKnowledge, now: datetime) -> MoveKey:
    known = reads_known(card, lemma, now)
    return MoveKey(card.note, known, known and not lemma.known_marked, card.choice)


def move(
    word: WordState, from_card: int, new_card_id: int, lemma: LemmaKnowledge, now: datetime,
) -> WordOutcome:
    """The decision moves from one card to a new, unbound card with the same content."""
    old = word.card(from_card)
    target = rule(MOVE_RULES, move_key(old, lemma, now))
    after = word.with_cards(
        CardState(from_card, target.old_card, _kept(old.binding, target.release)),
        CardState(new_card_id, target.new_card),
    )
    return WordOutcome(
        row=target.row,
        word=after,
        choices=(
            ChoiceChange(from_card, old.choice, target.old_card),
            ChoiceChange(new_card_id, _N, target.new_card),
        ),
        released=target.release,
        status=_change(word, after, lemma, now, Actor.USER),
        row_effects=target.effects,
    )


# --- export (§2.6) --------------------------------------------------------------------------


@dataclass(frozen=True)
class BindKey:
    role: Role
    note: NoteKind | None
    before: CardChoice


BIND_ROWS: tuple[tuple[BindKey, str], ...] = tuple(
    (BindKey(Role.DECISION, None, choice), "S1") for choice in (_L, _C)
)
BIND_RULES: Mapping[BindKey, str] = MappingProxyType(dict(BIND_ROWS))


def bind_key(word: WordState, card: CardState) -> BindKey:
    return BindKey(role_of(word, card), card.note, card.choice)


def on_bind(
    word: WordState, card_id: int, lemma: LemmaKnowledge, now: datetime,
) -> WordOutcome:
    """S1: the card being exported gets a new active binding; its timer starts now."""
    card = word.card(card_id)
    row = rule(BIND_RULES, bind_key(word, card))
    binding = Binding(KIND_OF_CHOICE[card.choice], learning_since=now)
    after = word.with_cards(CardState(card_id, card.choice, binding))
    return WordOutcome(
        row=row,
        word=after,
        choices=(),
        released=False,
        status=_change(word, after, lemma, now, Actor.EXPORT),
    )


# --- Known removal (§2.7) -----------------------------------------------------------------


@dataclass(frozen=True)
class RemovalKey:
    decision: CardChoice    # the word's decision card choice, NONE without one
    note: NoteKind | None
    reads_known: bool


@dataclass(frozen=True)
class RemovalTarget:
    row: str
    revoke: bool
    release: bool = False


_REMOVAL_CHOICES = DECISION_CHOICES | {CardChoice.NONE}


def possible_removal(key: RemovalKey) -> bool:
    return (
        key.decision in _REMOVAL_CHOICES
        and _holds_binding(key.note, key.decision)
        and (not key.reads_known or _learning(key.note, key.decision))
    )


_KEEP = RemovalTarget("R0", revoke=False)
REMOVAL_ROWS: tuple[tuple[RemovalKey, RemovalTarget], ...] = (
    (RemovalKey(_N, None, False), _KEEP),
    *((RemovalKey(c, None, False), _KEEP) for c in (_L, _C)),
    *((RemovalKey(CHOICE_OF_KIND[k], k, False), _KEEP) for k in NoteKind),
    (RemovalKey(_K, None, False), RemovalTarget("R1", revoke=True)),
    *((RemovalKey(_K, k, False), RemovalTarget("R2", True, release=True)) for k in NoteKind),
    *(
        (RemovalKey(CHOICE_OF_KIND[k], k, True), RemovalTarget("R3", True, release=True))
        for k in NoteKind
    ),
)
REMOVAL_RULES: Mapping[RemovalKey, RemovalTarget] = MappingProxyType(dict(REMOVAL_ROWS))


def removal_key(word: WordState, lemma: LemmaKnowledge, now: datetime) -> RemovalKey:
    card = word.decision
    return RemovalKey(card.choice, card.note, reads_known(card, lemma, now))


@dataclass(frozen=True)
class OrphanTarget:
    row: str
    release: bool


ORPHAN_RULES: Mapping[bool, OrphanTarget] = MappingProxyType(
    {True: OrphanTarget("O1", release=True), False: OrphanTarget("O0", release=False)},
)
"""Keyed by whether the orphaned binding's timer is due."""


def on_known_removed(
    lemma: LemmaKnowledge, words: Sequence[WordState], orphans: Iterable[BindingRef],
    now: datetime,
) -> KnownRemoval:
    """`lemma` is the snapshot taken before Known was forgotten; `words` are every word of
    the lemma in every source."""
    ruled = ((word, rule(REMOVAL_RULES, removal_key(word, lemma, now))) for word in words)
    return KnownRemoval(
        words=tuple(
            _revoked(word, target, lemma, now) for word, target in ruled if target.revoke
        ),
        released_orphans=tuple(
            ref.binding_id for ref in orphans
            if ORPHAN_RULES[timer_due(ref.learning_since, now)].release
        ),
    )


def _revoked(
    word: WordState, target: RemovalTarget, lemma: LemmaKnowledge, now: datetime,
) -> WordOutcome:
    card = word.decision
    after = word.with_cards(CardState(card.card_id, _N, _kept(card.binding, target.release)))
    return WordOutcome(
        row=target.row,
        word=after,
        choices=(ChoiceChange(card.card_id, card.choice, _N),),
        released=target.release,
        status=_change(word, after, lemma, now, Actor.REVOKE),
        row_effects=_RELEASE_EFFECTS[target.release],
    )


# --- effects (§2.8) -----------------------------------------------------------------------

_CHANGED: frozenset[Effect] = frozenset({Effect.REFRESH_SOURCE, Effect.REFRESH_LEMMA})
_CHOICE_ONLY: frozenset[Effect] = frozenset({Effect.REFRESH_SOURCE})
_NEW, _LEARN, _LEARNING, _KNOWN = (
    WordStatus.NEW, WordStatus.LEARN, WordStatus.LEARNING, WordStatus.KNOWN,
)
_STATUS_EFFECTS: Mapping[tuple[WordStatus, WordStatus, Actor], frozenset[Effect]] = (
    MappingProxyType({
        (_NEW, _LEARN, Actor.USER): frozenset({Effect.CALIBRATE}),
        (_NEW, _KNOWN, Actor.USER): frozenset({Effect.MARK_KNOWN, Effect.CALIBRATE}),
        (_LEARN, _NEW, Actor.USER): frozenset({Effect.FORGET_CALIBRATION}),
        (_LEARN, _KNOWN, Actor.USER): frozenset({Effect.MARK_KNOWN, Effect.CALIBRATE}),
        (_LEARNING, _KNOWN, Actor.USER): frozenset({Effect.MARK_KNOWN, Effect.CALIBRATE}),
        (_LEARNING, _NEW, Actor.USER): frozenset({Effect.FORGET_CALIBRATION}),
        (_LEARNING, _LEARN, Actor.USER): _NO_EFFECTS,
        (_KNOWN, _NEW, Actor.USER): frozenset(
            {Effect.REMOVE_KNOWN, Effect.FORGET_CALIBRATION},
        ),
        (_KNOWN, _LEARN, Actor.USER): frozenset({Effect.REMOVE_KNOWN, Effect.CALIBRATE}),
        (_LEARN, _LEARNING, Actor.EXPORT): frozenset({Effect.BIND}),
        (_LEARN, _KNOWN, Actor.EXPORT): frozenset({Effect.BIND}),
        (_KNOWN, _NEW, Actor.REVOKE): frozenset({Effect.FORGET_CALIBRATION}),
    })
)
EFFECTS: Mapping[tuple[WordStatus, WordStatus, Actor], frozenset[Effect]] = MappingProxyType(
    {
        **{(status, status, Actor.USER): _CHOICE_ONLY for status in WordStatus},
        **{change: listed | _CHANGED for change, listed in _STATUS_EFFECTS.items()},
    },
)


def effects(change: StatusChange) -> frozenset[Effect]:
    return rule(EFFECTS, (change.before, change.after, change.actor))
