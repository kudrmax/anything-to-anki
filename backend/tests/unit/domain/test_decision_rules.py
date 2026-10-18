"""The decision tables: every possible key has exactly one row, and every row keeps the
invariants A1, A2, AK and AR.

Worlds are generated: a word with the acted card and maybe a sibling, other sources of the
lemma, orphaned bindings, and the lemma's lists. Every key is derived from a world, never
written by hand, so the tests prove the tables cover what the app can be in.
"""
from __future__ import annotations

import contextlib
import itertools
from collections import defaultdict
from dataclasses import dataclass, replace
from functools import cache
from typing import Literal

import pytest
from backend.domain.exceptions import ActionRefusedError, NoDecisionRuleError
from backend.domain.services.decision_rules import (
    BIND_ROWS,
    BIND_RULES,
    EFFECTS,
    MOVE_ROWS,
    MOVE_RULES,
    PRESS_ROWS,
    PRESS_RULES,
    REMOVAL_ROWS,
    REMOVAL_RULES,
    BindingRef,
    BindKey,
    Effect,
    MoveKey,
    PressKey,
    RemovalKey,
    StatusChange,
    Target,
    WordOutcome,
    bind_key,
    effects,
    expand,
    move,
    move_key,
    on_bind,
    on_known_removed,
    possible,
    possible_move,
    possible_removal,
    press,
    press_key,
    removal_key,
)
from backend.domain.value_objects.card_choice import (
    CHOICE_OF_PRESS,
    Actor,
    Binding,
    CardChoice,
    CardState,
    DecisionStatus,
    NoteKind,
    Press,
    Refusal,
    Role,
    WordState,
    decision_status,
    export_kind,
    status_of,
)
from backend.domain.value_objects.learning_timer import timer_due
from backend.domain.value_objects.word_status import WordStatus

from tests.decision_worlds import (
    ACTED,
    DUE,
    FRESH,
    LEMMA,
    NEW_CARD,
    NOW,
    World,
    holds_ak,
    single,
    well_formed,
    worlds,
)

N, L, C, K, S = (
    CardChoice.NONE, CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP,
)
NEW, LEARN, LEARNING, KNOWN = (
    WordStatus.NEW, WordStatus.LEARN, WordStatus.LEARNING, WordStatus.KNOWN,
)
CHANGED = frozenset({Effect.REFRESH_SOURCE, Effect.REFRESH_LEMMA})
SAME = frozenset({Effect.REFRESH_SOURCE})
MK, RK = Effect.MARK_KNOWN, Effect.REMOVE_KNOWN
CAL, FORGET, REL = Effect.CALIBRATE, Effect.FORGET_CALIBRATION, Effect.RELEASE


def _changed(*extra: Effect) -> frozenset[Effect]:
    return CHANGED | frozenset(extra)


def _same(*extra: Effect) -> frozenset[Effect]:
    return SAME | frozenset(extra)




def _press(world: World, button: Press) -> WordOutcome:
    return press(world.word, ACTED, button, world.knowledge(), world.elsewhere(), NOW)


def _key(world: World, button: Press) -> PressKey:
    return press_key(world.word, ACTED, button, world.knowledge(), world.elsewhere(), NOW)


# --- the invariants after a row ----------------------------------------------------------


def _cascade(world: World) -> World:
    removal = on_known_removed(world.knowledge(), world.words, world.orphans, NOW)
    after = world.replacing(*(outcome.word for outcome in removal.words))
    return replace(
        after, known_marked=False,
        orphans=tuple(o for o in world.orphans if o.binding_id not in removal.released_orphans),
    )


def _settle(world: World, outcome: WordOutcome) -> World:
    """Applies the outcome's word and its knowledge effects to the world."""
    after = world.replacing(outcome.word)
    if Effect.MARK_KNOWN in outcome.effects:
        after = replace(after, known_marked=True, unknown=False)
    if Effect.REMOVE_KNOWN in outcome.effects:
        after = _cascade(after)
    return after


def _assert_ar(world: World) -> None:
    knowledge = world.knowledge()
    assert knowledge.is_known is False
    assert all(status_of(word, knowledge, NOW) is not KNOWN for word in world.words)


def _assert_invariants(before: World, outcome: WordOutcome) -> None:
    assert outcome.status.after is status_of(outcome.word, before.knowledge(), NOW)
    after = _settle(before, outcome)
    assert all(well_formed(word) for word in after.words), "A1/A2"
    assert holds_ak(after), "AK"
    if Effect.REMOVE_KNOWN in outcome.effects:
        _assert_ar(after)


# --- press: expansion -------------------------------------------------------------------


def _all_press_keys() -> list[PressKey]:
    return [
        PressKey(role, note, reads_known, elsewhere, before, button)
        for role, note, reads_known, elsewhere, before, button in itertools.product(
            Role, (None, *NoteKind), (False, True), (False, True), CardChoice, Press,
        )
    ]


@pytest.mark.unit
class TestPressExpansion:
    def test_rows_expand_to_unique_keys(self) -> None:
        keys = [key for row in PRESS_ROWS for key in expand(row)]
        assert len(keys) == len(set(keys)) == len(PRESS_RULES)

    def test_every_possible_key_is_covered_exactly_once(self) -> None:
        assert {key for key in _all_press_keys() if possible(key)} == set(PRESS_RULES)
        assert len(PRESS_RULES) == 60

    def test_every_reachable_key_is_possible(self) -> None:
        reached = {_key(world, button) for world in worlds() for button in Press}
        assert all(possible(key) for key in reached)
        assert reached == set(PRESS_RULES), "the worlds reach every possible key"

    def test_no_key_yields_in_anki(self) -> None:
        refusals = {t.refusal for t in PRESS_RULES.values() if t.refusal is not None}
        assert refusals == {Refusal.NOT_DECISION_CARD, Refusal.DECIDED_ELSEWHERE}

    @pytest.mark.parametrize(("choice", "release"), [(L, False), (N, True)])
    def test_a_refusal_row_neither_chooses_nor_releases(
        self, choice: CardChoice, release: bool,
    ) -> None:
        with pytest.raises(ValueError, match="refusal row"):
            Target("P0", choice, release, Refusal.NOT_DECISION_CARD)

    def test_grant_is_the_choice_or_the_refusal(self) -> None:
        assert Target("P0", K).grant(ACTED) is K
        with pytest.raises(ActionRefusedError) as refused:
            Target("P0", refusal=Refusal.DECIDED_ELSEWHERE).grant(ACTED)
        assert (refused.value.card_id, refused.value.refusal) == (
            ACTED, Refusal.DECIDED_ELSEWHERE,
        )

    def test_an_impossible_state_has_no_rule(self) -> None:
        word = WordState(1, LEMMA, "verb", 1, (CardState(ACTED, S, Binding(NoteKind.LEARN, NOW)),))
        knowledge = World(word, (), (), False, False).knowledge()
        with pytest.raises(NoDecisionRuleError):
            press(word, ACTED, Press.LEARN, knowledge, None, NOW)


# --- press: one test per row --------------------------------------------------------------

PRESSED: Literal["pressed"] = "pressed"


@dataclass(frozen=True)
class Expected:
    choice: CardChoice | Refusal | Literal["pressed"]
    release: bool = False
    status: tuple[WordStatus, WordStatus] | None = None   # None: unchanged
    effects: frozenset[Effect] = SAME


PRESS_EXPECTED: dict[str, Expected] = {
    "P1": Expected(L, status=(NEW, LEARN), effects=_changed(CAL)),
    "P2": Expected(C, status=(NEW, LEARN), effects=_changed(CAL)),
    "P3": Expected(K, status=(NEW, KNOWN), effects=_changed(MK, CAL)),
    "P4": Expected(S),
    "P5": Expected(N),
    "P6": Expected(Refusal.DECIDED_ELSEWHERE),
    "P7": Expected(S),
    "P8": Expected(N),
    "P9": Expected(N, status=(LEARN, NEW), effects=_changed(FORGET)),
    "P10": Expected(PRESSED),
    "P11": Expected(K, status=(LEARN, KNOWN), effects=_changed(MK, CAL)),
    "P12": Expected(S, status=(LEARN, NEW), effects=_changed(FORGET)),
    "P13": Expected(N, status=(KNOWN, NEW), effects=_changed(RK, FORGET)),
    "P14": Expected(PRESSED, status=(KNOWN, LEARN), effects=_changed(RK, CAL)),
    "P15": Expected(S, status=(KNOWN, NEW), effects=_changed(RK, FORGET)),
    "P16": Expected(K, status=(LEARNING, KNOWN), effects=_changed(MK, CAL)),
    "P17": Expected(N, True, (LEARNING, NEW), _changed(FORGET, REL)),
    "P18": Expected(PRESSED, True, (LEARNING, LEARN), _changed(REL)),
    "P19": Expected(S, True, (LEARNING, NEW), _changed(FORGET, REL)),
    "P20": Expected(N, True, (KNOWN, NEW), _changed(RK, FORGET, REL)),
    "P21": Expected(S, True, (KNOWN, NEW), _changed(RK, FORGET, REL)),
    "P22": Expected(PRESSED, True, (KNOWN, LEARN), _changed(RK, CAL, REL)),
    "P23": Expected(N, True, (KNOWN, NEW), _changed(RK, FORGET, REL)),
    "P24": Expected(PRESSED, True, (KNOWN, LEARN), _changed(RK, CAL, REL)),
    "P24s": Expected(S, True, (KNOWN, NEW), _changed(RK, FORGET, REL)),
    "P25": Expected(Refusal.NOT_DECISION_CARD),
    "P26": Expected(N),
    "P27": Expected(Refusal.NOT_DECISION_CARD),
}


@cache
def _press_cases() -> dict[str, tuple[tuple[World, Press], ...]]:
    by_row: dict[str, list[tuple[World, Press]]] = defaultdict(list)
    for world in worlds():
        for button in Press:
            by_row[PRESS_RULES[_key(world, button)].row].append((world, button))
    return {row: tuple(cases) for row, cases in by_row.items()}


@pytest.mark.unit
class TestPressRows:
    def test_the_rows_are_p1_to_p27(self) -> None:
        assert {t.row for t in PRESS_RULES.values()} == set(PRESS_EXPECTED)

    @pytest.mark.parametrize("row", list(PRESS_EXPECTED))
    def test_row(self, row: str) -> None:
        expected = PRESS_EXPECTED[row]
        cases = _press_cases()[row]
        assert cases
        for world, button in cases:
            if isinstance(expected.choice, Refusal):
                with pytest.raises(ActionRefusedError) as refused:
                    _press(world, button)
                assert refused.value.refusal is expected.choice
                assert refused.value.card_id == ACTED
                continue
            self._assert_row(row, expected, world, button)

    @staticmethod
    def _assert_row(row: str, expected: Expected, world: World, button: Press) -> None:
        before = world.word.card(ACTED)
        outcome = _press(world, button)
        card = outcome.word.card(ACTED)
        choice = CHOICE_OF_PRESS[button] if expected.choice == PRESSED else expected.choice
        assert outcome.row == row
        assert card.choice is choice
        assert outcome.released is expected.release
        assert card.binding == (None if expected.release else before.binding)
        assert outcome.choices[0].before is before.choice
        assert outcome.choices[0].after is choice
        status = outcome.status
        assert (status.word_id, status.actor) == (world.word.word_id, Actor.USER)
        if expected.status is None:
            assert status.before is status.after
        else:
            assert (status.before, status.after) == expected.status
        assert outcome.effects == expected.effects
        assert [c for c in outcome.word.cards if c.card_id != ACTED] == [
            c for c in world.word.cards if c.card_id != ACTED
        ]
        _assert_invariants(world, outcome)


@pytest.mark.unit
class TestKnownRemovalAfterAPress:
    """P20 / P23 / P24s: NEW with release, and every Known card of the lemma goes NEW."""

    def _world(self, acted: CardState, *, known_marked: bool) -> World:
        return World(
            WordState(1, LEMMA, "verb", 1, (acted,)),
            (
                single(2, K),                                        # explicit Known
                single(3, L, Binding(NoteKind.LEARN, FRESH)),         # list-Known if marked
                single(4, C, Binding(NoteKind.CLOZE, DUE)),           # timer-Known
                single(5, L),                                        # Learn, not exported
                single(6, S),                                        # no decision
            ) if known_marked else (
                single(3, L, Binding(NoteKind.LEARN, FRESH)),         # Learning, timer runs
                single(4, C, Binding(NoteKind.CLOZE, DUE)),           # timer-Known
                single(5, L),
            ),
            (BindingRef(501, DUE), BindingRef(502, FRESH)),
            known_marked, False,
        )

    @pytest.mark.parametrize(
        ("acted", "button", "known_marked"),
        [
            (CardState(ACTED, K, Binding(NoteKind.LEARN, FRESH)), Press.KNOWN, True),     # P20
            (CardState(ACTED, L, Binding(NoteKind.LEARN, DUE)), Press.KNOWN, False),      # P23
            (CardState(ACTED, L, Binding(NoteKind.LEARN, FRESH)), Press.KNOWN, True),     # P23
            (CardState(ACTED, C, Binding(NoteKind.CLOZE, DUE)), Press.SKIP, False),       # P24s
        ],
    )
    def test_every_known_card_of_the_lemma_goes_new(
        self, acted: CardState, button: Press, known_marked: bool,
    ) -> None:
        world = self._world(acted, known_marked=known_marked)
        outcome = _press(world, button)
        assert outcome.status.after is NEW
        assert outcome.word.card(ACTED).binding is None
        assert Effect.REMOVE_KNOWN in outcome.effects

        pressed = world.replacing(outcome.word)
        snapshot = pressed.knowledge()
        removal = on_known_removed(snapshot, pressed.words, pressed.orphans, NOW)
        revoked = {o.word.word_id: o for o in removal.words}
        read_known = {
            w.word_id for w in pressed.words if status_of(w, snapshot, NOW) is KNOWN
        }
        assert set(revoked) == read_known
        assert read_known >= ({2, 3, 4} if known_marked else {4})
        for word_id, outcome_of in revoked.items():
            assert outcome_of.status == StatusChange(word_id, KNOWN, NEW, Actor.REVOKE)
            assert outcome_of.word.decision_card is None
            assert all(card.binding is None for card in outcome_of.word.cards)
        assert removal.released_orphans == (501,)
        untouched = {w.word_id for w in pressed.words} - set(revoked)
        assert untouched >= {1, 5}
        _assert_ar(_cascade(pressed))

    def test_the_cascade_reads_the_snapshot_before_forgetting(self) -> None:
        world = self._world(CardState(ACTED, K), known_marked=True)
        forgotten = replace(world, known_marked=False).knowledge()
        before = on_known_removed(world.knowledge(), world.words, world.orphans, NOW)
        after = on_known_removed(forgotten, world.words, world.orphans, NOW)
        assert 3 in {o.word.word_id for o in before.words}
        assert 3 not in {o.word.word_id for o in after.words}

    def test_learning_cards_that_do_not_read_known_stay(self) -> None:
        world = self._world(CardState(ACTED, L, Binding(NoteKind.LEARN, DUE)), known_marked=False)
        removal = on_known_removed(world.knowledge(), world.words, world.orphans, NOW)
        assert {o.word.word_id for o in removal.words} == {1, 4}
        assert 502 not in removal.released_orphans


# --- move (Replace with example) -------------------------------------------------------


def _all_move_keys() -> list[MoveKey]:
    return [
        MoveKey(note, reads_known, timer_only, before)
        for note, reads_known, timer_only, before in itertools.product(
            (None, *NoteKind), (False, True), (False, True), CardChoice,
        )
    ]


def _move(world: World) -> WordOutcome:
    return move(world.word, ACTED, NEW_CARD, world.knowledge(), NOW)


def _move_key(world: World) -> MoveKey:
    return move_key(world.word.card(ACTED), world.knowledge(), NOW)


@dataclass(frozen=True)
class ExpectedMove:
    new_card: CardChoice | Literal["before"]
    old_card: CardChoice | Literal["before"]
    release: bool
    status: tuple[WordStatus, WordStatus] | None
    effects: frozenset[Effect]


MOVE_EXPECTED: dict[tuple[str, bool], ExpectedMove] = {
    ("M1", False): ExpectedMove("before", N, False, None, SAME),
    ("M2", False): ExpectedMove(N, "before", False, None, SAME),
    ("M3a", False): ExpectedMove(K, N, True, (KNOWN, KNOWN), _changed(REL)),
    ("M3k", False): ExpectedMove(K, N, True, (KNOWN, KNOWN), _changed(REL)),
    ("M3k", True): ExpectedMove(K, N, True, (KNOWN, KNOWN), _changed(REL, MK)),
    ("M3b", False): ExpectedMove("before", N, True, (LEARNING, LEARN), _changed(REL)),
}


@pytest.mark.unit
class TestMoveRows:
    def test_rows_are_unique(self) -> None:
        assert len(MOVE_ROWS) == len(MOVE_RULES)

    def test_every_possible_key_is_covered_exactly_once(self) -> None:
        assert {key for key in _all_move_keys() if possible_move(key)} == set(MOVE_RULES)

    def test_every_reachable_key_is_possible(self) -> None:
        reached = {_move_key(world) for world in worlds()}
        assert reached == set(MOVE_RULES)

    def test_the_rows_are_m1_to_m3b(self) -> None:
        assert {t.row for t in MOVE_RULES.values()} == {"M1", "M2", "M3a", "M3k", "M3b"}

    @pytest.mark.parametrize(("row", "timer_only"), list(MOVE_EXPECTED))
    def test_row(self, row: str, timer_only: bool) -> None:
        expected = MOVE_EXPECTED[row, timer_only]
        cases = [
            w for w in worlds()
            if MOVE_RULES[_move_key(w)].row == row and _move_key(w).timer_only is timer_only
        ]
        assert cases
        for world in cases:
            before = world.word.card(ACTED)
            outcome = _move(world)
            old, new = outcome.word.card(ACTED), outcome.word.card(NEW_CARD)
            assert outcome.row == row
            assert new.choice is (before.choice if expected.new_card == "before"
                                  else expected.new_card)
            assert old.choice is (before.choice if expected.old_card == "before"
                                  else expected.old_card)
            assert new.binding is None
            assert outcome.released is expected.release
            assert old.binding == (None if expected.release else before.binding)
            if expected.status is None:
                assert outcome.status.before is outcome.status.after
            else:
                assert (outcome.status.before, outcome.status.after) == expected.status
            assert outcome.effects == expected.effects
            assert Effect.REMOVE_KNOWN not in outcome.effects
            _assert_invariants(world, outcome)

    def test_m3b_requeues_for_export(self) -> None:
        for world in worlds():
            if MOVE_RULES[_move_key(world)].row == "M3b":
                assert decision_status(_move(world).word) is DecisionStatus.LEARN

    def test_m3_keeps_a_known_word_known(self) -> None:
        for world in worlds():
            if MOVE_RULES[_move_key(world)].row in {"M3a", "M3k"}:
                settled = _settle(world, _move(world))
                assert status_of(settled.word, settled.knowledge(), NOW) is KNOWN


# --- export (S1) ------------------------------------------------------------------------


@pytest.mark.unit
class TestBindRows:
    def test_s1_is_the_only_row(self) -> None:
        assert set(BIND_RULES.values()) == {"S1"}
        assert len(BIND_ROWS) == len(BIND_RULES)
        assert set(BIND_RULES) == {
            BindKey(Role.DECISION, None, L), BindKey(Role.DECISION, None, C),
        }

    def test_s1_binds_with_the_timer_starting_now(self) -> None:
        cases = [w for w in worlds() if bind_key(w.word, w.word.card(ACTED)) in BIND_RULES]
        assert cases
        for world in cases:
            before = world.word.card(ACTED)
            outcome = on_bind(world.word, ACTED, world.knowledge(), NOW)
            card = outcome.word.card(ACTED)
            assert outcome.row == "S1"
            assert card.choice is before.choice
            assert card.binding == Binding(export_kind(before) or NoteKind.LEARN, NOW)
            assert export_kind(before) is not None
            listed = world.known_marked and not world.unknown
            after = KNOWN if listed else LEARNING
            assert outcome.status == StatusChange(1, LEARN, after, Actor.EXPORT)
            assert outcome.effects == _changed(Effect.BIND)
            assert outcome.released is False
            _assert_invariants(world, outcome)

    def test_any_other_card_has_no_bind_rule(self) -> None:
        for world in worlds():
            if bind_key(world.word, world.word.card(ACTED)) not in BIND_RULES:
                with pytest.raises(NoDecisionRuleError):
                    on_bind(world.word, ACTED, world.knowledge(), NOW)


# --- Known removal (R1-R3) -----------------------------------------------------------------


def _all_removal_keys() -> list[RemovalKey]:
    return [
        RemovalKey(decision, note, reads_known)
        for decision, note, reads_known in itertools.product(
            CardChoice, (None, *NoteKind), (False, True),
        )
    ]


@pytest.mark.unit
class TestRemovalRows:
    def test_rows_are_unique(self) -> None:
        assert len(REMOVAL_ROWS) == len(REMOVAL_RULES)

    def test_every_possible_key_is_covered_exactly_once(self) -> None:
        assert {k for k in _all_removal_keys() if possible_removal(k)} == set(REMOVAL_RULES)

    def test_every_reachable_key_is_possible(self) -> None:
        reached = {
            removal_key(word, world.knowledge(), NOW) for world in worlds() for word in world.words
        }
        assert reached == set(REMOVAL_RULES)

    @pytest.mark.parametrize(
        ("row", "release"), [("R1", False), ("R2", True), ("R3", True)],
    )
    def test_row(self, row: str, release: bool) -> None:
        seen = 0
        for world in worlds():
            knowledge = world.knowledge()
            removal = on_known_removed(knowledge, world.words, world.orphans, NOW)
            for outcome in removal.words:
                if outcome.row != row:
                    continue
                seen += 1
                before = next(w for w in world.words if w.word_id == outcome.word.word_id)
                card = before.decision_card
                assert card is not None
                assert outcome.word.card(card.card_id).choice is N
                assert outcome.word.card(card.card_id).binding is None
                assert outcome.released is release
                assert (card.binding is not None) is release
                assert outcome.status == StatusChange(before.word_id, KNOWN, NEW, Actor.REVOKE)
                assert outcome.effects == _changed(FORGET, *((REL,) if release else ()))
        assert seen

    def test_every_word_that_reads_known_is_revoked_and_no_other(self) -> None:
        for world in worlds():
            knowledge = world.knowledge()
            removal = on_known_removed(knowledge, world.words, world.orphans, NOW)
            reading_known = {
                w.word_id for w in world.words if status_of(w, knowledge, NOW) is KNOWN
            }
            assert {o.word.word_id for o in removal.words} == reading_known
            assert removal.released_orphans == tuple(
                o.binding_id for o in world.orphans if timer_due(o.learning_since, NOW)
            )
            after = _cascade(world)
            assert all(well_formed(word) for word in after.words)
            _assert_ar(after)

    def test_the_cascade_does_not_chain(self) -> None:
        for world in worlds():
            removal = on_known_removed(world.knowledge(), world.words, world.orphans, NOW)
            assert all(Effect.REMOVE_KNOWN not in o.effects for o in removal.words)


# --- effects --------------------------------------------------------------------------------


def _produced_changes() -> set[tuple[WordStatus, WordStatus, Actor]]:
    outcomes: list[WordOutcome] = []
    for world in worlds():
        for button in Press:
            with contextlib.suppress(ActionRefusedError):
                outcomes.append(_press(world, button))
        outcomes.append(_move(world))
        if bind_key(world.word, world.word.card(ACTED)) in BIND_RULES:
            outcomes.append(on_bind(world.word, ACTED, world.knowledge(), NOW))
        outcomes.extend(
            on_known_removed(world.knowledge(), world.words, world.orphans, NOW).words,
        )
    return {(o.status.before, o.status.after, o.status.actor) for o in outcomes}


@pytest.mark.unit
class TestEffects:
    def test_effects_are_total_over_every_produced_change(self) -> None:
        assert _produced_changes() == set(EFFECTS)

    def test_every_status_change_refreshes_the_source_and_the_lemma(self) -> None:
        for (before, after, _), table_effects in EFFECTS.items():
            expected = CHANGED if before is not after else SAME
            assert table_effects >= expected

    @pytest.mark.parametrize(
        ("before", "after", "actor", "expected"),
        [
            (NEW, LEARN, Actor.USER, _changed(CAL)),
            (NEW, KNOWN, Actor.USER, _changed(MK, CAL)),
            (LEARN, NEW, Actor.USER, _changed(FORGET)),
            (LEARN, KNOWN, Actor.USER, _changed(MK, CAL)),
            (LEARNING, KNOWN, Actor.USER, _changed(MK, CAL)),
            (LEARNING, NEW, Actor.USER, _changed(FORGET)),
            (LEARNING, LEARN, Actor.USER, CHANGED),
            (KNOWN, NEW, Actor.USER, _changed(RK, FORGET)),
            (KNOWN, LEARN, Actor.USER, _changed(RK, CAL)),
            (LEARN, LEARNING, Actor.EXPORT, _changed(Effect.BIND)),
            (LEARN, KNOWN, Actor.EXPORT, _changed(Effect.BIND)),
            (KNOWN, NEW, Actor.REVOKE, _changed(FORGET)),
            *((status, status, Actor.USER, SAME) for status in WordStatus),
        ],
    )
    def test_the_table(
        self, before: WordStatus, after: WordStatus, actor: Actor, expected: frozenset[Effect],
    ) -> None:
        assert effects(StatusChange(1, before, after, actor)) == expected

    def test_a_change_missing_from_the_table_is_a_bug(self) -> None:
        with pytest.raises(NoDecisionRuleError):
            effects(StatusChange(1, NEW, LEARNING, Actor.USER))
