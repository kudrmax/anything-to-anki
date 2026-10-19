"""The card view: every value a card shows is derived from the decision tables."""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import ActionRefusedError
from backend.domain.services.card_view import (
    NOTE_RULES,
    CardView,
    Command,
    NoteKey,
    Shown,
    Where,
    card_is_done,
    card_view,
    chosen_to_learn,
    in_export_queue,
    is_protected,
    keeps_word,
    note_key,
    possible_note,
    progress,
    reach,
    section,
    stored_chosen_to_learn,
    stored_decided,
)
from backend.domain.services.decision_rules import PRESS_RULES, press, press_key
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    Press,
    Role,
    WordState,
    status_of,
)
from backend.domain.value_objects.card_note import CardNote
from backend.domain.value_objects.decision_progress import DecisionProgress, ReviewReach
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.domain.value_objects.user_work import NO_USER_WORK
from backend.domain.value_objects.word_status import WordStatus

from tests.decision_worlds import ACTED, DUE, FRESH, LEMMA, NOW, SIBLING, World, worlds

if TYPE_CHECKING:
    from datetime import datetime

N, L, C, K, S = (
    CardChoice.NONE, CardChoice.LEARN, CardChoice.CLOZE, CardChoice.KNOWN, CardChoice.SKIP,
)


def _view_of(world: World) -> CardView:
    return card_view(world.word, ACTED, world.knowledge(), world.elsewhere(), NOW)


# --- properties over every generated world ------------------------------------------------


@pytest.mark.unit
class TestButtonsFollowTheTable:
    def test_command_is_set_exactly_when_the_press_is_allowed(self) -> None:
        for world in worlds():
            view = _view_of(world)
            assert [b.button for b in view.buttons] == list(Press)
            for button in view.buttons:
                try:
                    outcome = press(
                        world.word, ACTED, button.button, world.knowledge(), world.elsewhere(),
                        NOW,
                    )
                except ActionRefusedError as refused:
                    assert button.command is None
                    assert button.refused is refused.refusal
                    continue
                assert button.command is not None
                assert button.refused is None
                cloze_editor = (
                    button.button is Press.CLOZE and outcome.word.card(ACTED).choice is C
                )
                assert (button.command is Command.EDIT_CLOZE) is cloze_editor

    def test_on_decision_and_open_cards_pressed_means_pressing_unpresses(self) -> None:
        for world in worlds():
            knowledge, elsewhere = world.knowledge(), world.elsewhere()
            view = _view_of(world)
            for button in view.buttons:
                key = press_key(world.word, ACTED, button.button, knowledge, elsewhere, NOW)
                if key.role is Role.OTHER:
                    continue
                target = PRESS_RULES[key]
                unpresses = target.refusal is None and target.choice is N
                assert button.pressed is unpresses

    def test_a_decided_card_has_its_decision_pressed(self) -> None:
        for world in worlds():
            role = press_key(
                world.word, ACTED, Press.SKIP, world.knowledge(), world.elsewhere(), NOW,
            ).role
            deciding = [
                b.button for b in _view_of(world).buttons
                if b.pressed and b.button is not Press.SKIP
            ]
            assert len(deciding) == (0 if role is Role.OPEN else 1)

    def test_skip_is_pressed_exactly_on_a_skip_card(self) -> None:
        for world in worlds():
            skip = next(b for b in _view_of(world).buttons if b.button is Press.SKIP)
            assert skip.pressed is (world.word.card(ACTED).choice is S)

    def test_a_card_that_reads_known_has_known_pressed(self) -> None:
        for world in worlds():
            word, knowledge = world.word, world.knowledge()
            if status_of(word, knowledge, NOW) is not WordStatus.KNOWN:
                continue
            if press_key(word, ACTED, Press.KNOWN, knowledge, None, NOW).role is Role.OPEN:
                continue
            pressed = {b.button for b in _view_of(world).buttons if b.pressed}
            assert pressed - {Press.SKIP} == {Press.KNOWN}


@pytest.mark.unit
class TestDerivedConsistency:
    def test_is_done_is_a_status_or_a_skip(self) -> None:
        for world in worlds():
            view = _view_of(world)
            assert view.is_done is (
                view.shown.status is not WordStatus.NEW or view.shown.skipped
            )

    def test_a_decided_word_shows_its_status_of(self) -> None:
        for world in worlds():
            view = _view_of(world)
            if view.shown.where in {Where.HERE, Where.OTHER_CARD}:
                assert view.shown.status is status_of(world.word, world.knowledge(), NOW)

    def test_every_possible_note_key_has_one_row(self) -> None:
        keys = [
            NoteKey(*fields) for fields in itertools.product(
                Role, (False, True), (False, True), (False, True), (False, True),
                (None, *ElsewhereStatus), (False, True), (False, True),
            )
        ]
        assert {key for key in keys if possible_note(key)} == set(NOTE_RULES)

    def test_every_reachable_note_key_is_ruled(self) -> None:
        reached = {
            note_key(w.word, w.word.card(ACTED), w.knowledge(), w.elsewhere(), NOW)
            for w in worlds()
        }
        assert reached == set(NOTE_RULES)

    def test_can_edit_cloze_is_an_unbound_cloze(self) -> None:
        for world in worlds():
            card = world.word.card(ACTED)
            assert _view_of(world).can_edit_cloze is (card.choice is C and card.binding is None)


# --- one test per derived value per state class --------------------------------------------


@dataclass(frozen=True)
class State:
    word: WordState
    known_marked: bool = False
    elsewhere: ElsewhereStatus | None = None
    unknown: bool = False

    def knowledge(self) -> LemmaKnowledge:
        since = tuple(c.binding.learning_since for c in self.word.cards if c.binding)
        return LemmaKnowledge.at(
            NOW, known_marked=self.known_marked, unknown=self.unknown, learn_anywhere=False,
            active_since=since,
        )

    def view(self) -> CardView:
        return card_view(self.word, ACTED, self.knowledge(), self.elsewhere, NOW)


def _word(*cards: CardState) -> WordState:
    return WordState(1, LEMMA, "verb", 1, cards)


def _card(choice: CardChoice, kind: NoteKind | None = None, since: datetime = FRESH) -> CardState:
    return CardState(ACTED, choice, None if kind is None else Binding(kind, since))


STATES: dict[str, State] = {
    "open_new": State(_word(_card(N))),
    "open_skip": State(_word(_card(S))),
    "open_known_elsewhere": State(_word(_card(N)), True, ElsewhereStatus.KNOWN),
    "open_learning_elsewhere": State(_word(_card(N)), elsewhere=ElsewhereStatus.LEARNING),
    "open_learn_elsewhere": State(_word(_card(N)), elsewhere=ElsewhereStatus.LEARN),
    "learn": State(_word(_card(L))),
    "cloze": State(_word(_card(C))),
    "known": State(_word(_card(K)), known_marked=True),
    "learning": State(_word(_card(L, NoteKind.LEARN))),
    "learning_cloze": State(_word(_card(C, NoteKind.CLOZE))),
    "known_by_timer": State(_word(_card(L, NoteKind.LEARN, DUE))),
    "known_by_list": State(_word(_card(L, NoteKind.LEARN)), known_marked=True),
    # Q15: Learn, then the lemma was put in Known before the export.
    "learn_then_listed": State(_word(_card(L)), known_marked=True),
    "known_in_anki": State(_word(_card(K, NoteKind.LEARN)), known_marked=True),
    "in_anki_unknown": State(_word(_card(L, NoteKind.LEARN, DUE)), unknown=True),
    "other_open": State(_word(_card(N), CardState(SIBLING, L))),
    "other_skip": State(_word(_card(S), CardState(SIBLING, K)), known_marked=True),
}
KNOWN_ON_FRESH = FRESH + LEARNING_KNOWN_AFTER
_NEW, _LEARN, _LEARNING, _KNOWN = (
    WordStatus.NEW, WordStatus.LEARN, WordStatus.LEARNING, WordStatus.KNOWN,
)


def _per_state(expected: dict[str, object]) -> list[tuple[str, object]]:
    assert set(expected) == set(STATES)
    return list(expected.items())


@pytest.mark.unit
class TestPerState:
    @pytest.mark.parametrize(("state", "expected"), _per_state({
        "open_new": set(), "open_skip": {Press.SKIP}, "open_known_elsewhere": set(),
        "open_learning_elsewhere": set(), "open_learn_elsewhere": set(),
        "learn": {Press.LEARN}, "cloze": {Press.CLOZE}, "known": {Press.KNOWN},
        "learning": {Press.LEARN}, "learning_cloze": {Press.CLOZE},
        "known_by_timer": {Press.KNOWN}, "known_by_list": {Press.KNOWN},
        "learn_then_listed": {Press.KNOWN}, "known_in_anki": {Press.KNOWN},
        "in_anki_unknown": {Press.LEARN},
        "other_open": {Press.LEARN},
        "other_skip": {Press.KNOWN, Press.SKIP},
    }))
    def test_pressed(self, state: str, expected: set[Press]) -> None:
        assert {b.button for b in STATES[state].view().buttons if b.pressed} == expected

    @pytest.mark.parametrize(("state", "expected"), _per_state({
        "open_new": (None, None), "open_skip": (None, None),
        "open_known_elsewhere": (CardNote.KNOWN_ELSEWHERE, None),
        "open_learning_elsewhere": (CardNote.LEARNING_ELSEWHERE, None),
        "open_learn_elsewhere": (CardNote.LEARN_ELSEWHERE, None),
        "learn": (None, None), "cloze": (None, None), "known": (None, None),
        "learning": (CardNote.IN_ANKI, KNOWN_ON_FRESH),
        "learning_cloze": (CardNote.IN_ANKI, KNOWN_ON_FRESH),
        "known_by_timer": (CardNote.KNOWN_BY_TIMER, None),
        "known_by_list": (CardNote.KNOWN_BY_LIST, None),
        "learn_then_listed": (CardNote.KNOWN_BY_LIST, None),
        "known_in_anki": (CardNote.IN_ANKI, None),
        "in_anki_unknown": (CardNote.IN_ANKI, None),
        "other_open": (CardNote.LEARNED_ON_OTHER_CARD, None),
        "other_skip": (CardNote.KNOWN_ON_OTHER_CARD, None),
    }))
    def test_note(self, state: str, expected: tuple[CardNote | None, datetime | None]) -> None:
        view = STATES[state].view()
        assert (view.note, view.known_on) == expected

    @pytest.mark.parametrize(("state", "expected"), _per_state({
        "open_new": Shown(_NEW, False, Where.NOWHERE),
        "open_skip": Shown(_NEW, True, Where.NOWHERE),
        "open_known_elsewhere": Shown(_KNOWN, False, Where.OTHER_SOURCE),
        "open_learning_elsewhere": Shown(_LEARNING, False, Where.OTHER_SOURCE),
        "open_learn_elsewhere": Shown(_LEARN, False, Where.OTHER_SOURCE),
        "learn": Shown(_LEARN, False, Where.HERE),
        "cloze": Shown(_LEARN, False, Where.HERE),
        "known": Shown(_KNOWN, False, Where.HERE),
        "learning": Shown(_LEARNING, False, Where.HERE),
        "learning_cloze": Shown(_LEARNING, False, Where.HERE),
        "known_by_timer": Shown(_KNOWN, False, Where.HERE),
        "known_by_list": Shown(_KNOWN, False, Where.HERE),
        "learn_then_listed": Shown(_KNOWN, False, Where.HERE),
        "known_in_anki": Shown(_KNOWN, False, Where.HERE),
        "in_anki_unknown": Shown(_LEARNING, False, Where.HERE),
        "other_open": Shown(_LEARN, False, Where.OTHER_CARD),
        "other_skip": Shown(_KNOWN, True, Where.OTHER_CARD),
    }))
    def test_shown(self, state: str, expected: Shown) -> None:
        assert STATES[state].view().shown == expected

    @pytest.mark.parametrize(("state", "expected"), _per_state(
        {name: name != "open_new" for name in STATES},
    ))
    def test_is_done(self, state: str, expected: bool) -> None:
        assert STATES[state].view().is_done is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state(
        {name: name == "cloze" for name in STATES},
    ))
    def test_can_edit_cloze(self, state: str, expected: bool) -> None:
        assert STATES[state].view().can_edit_cloze is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state({
        name: name not in {
            "open_new", "open_known_elsewhere", "open_learning_elsewhere",
            "open_learn_elsewhere", "other_open",
        } for name in STATES
    }))
    def test_is_protected(self, state: str, expected: bool) -> None:
        assert is_protected(STATES[state].word.card(ACTED), NO_USER_WORK) is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state({
        name: name not in {
            "open_new", "open_known_elsewhere", "open_learning_elsewhere",
            "open_learn_elsewhere",
        } for name in STATES
    }))
    def test_keeps_word(self, state: str, expected: bool) -> None:
        assert keeps_word(STATES[state].word, {}) is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state(
        {name: name in {"learn", "cloze", "other_open"} for name in STATES},
    ))
    def test_in_export_queue(self, state: str, expected: bool) -> None:
        the_state = STATES[state]
        assert in_export_queue(the_state.word, the_state.knowledge(), NOW) is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state({
        name: name in {
            "learn", "cloze", "learning", "learning_cloze", "known_by_timer",
            "known_by_list", "learn_then_listed", "in_anki_unknown", "other_open",
        } for name in STATES
    }))
    def test_chosen_to_learn(self, state: str, expected: bool) -> None:
        assert chosen_to_learn(STATES[state].word) is expected

    @pytest.mark.parametrize(("state", "expected"), _per_state(
        {name: name in {"open_new", "learn", "cloze"} for name in STATES},
    ))
    def test_wants_generation(self, state: str, expected: bool) -> None:
        assert STATES[state].view().wants_generation is expected

    @pytest.mark.parametrize(
        ("state", "open_section"),
        list(itertools.product(STATES, (CandidateSection.READY, CandidateSection.EXTRA))),
    )
    def test_section(self, state: str, open_section: CandidateSection) -> None:
        view = STATES[state].view()
        expected = CandidateSection.REVIEWED if view.is_done else open_section
        assert section(view, open_section) is expected

    def test_a_skipped_card_with_the_word_known_shows_known(self) -> None:
        assert STATES["other_skip"].view().shown.status is _KNOWN


@pytest.mark.unit
class TestProgress:
    def test_reviewed_over_reviewed_and_open_ready(self) -> None:
        sections = [
            CandidateSection.REVIEWED, CandidateSection.REVIEWED, CandidateSection.READY,
            CandidateSection.READY, CandidateSection.EXTRA, CandidateSection.PROBABLY_KNOWN,
        ]
        assert progress(sections) == DecisionProgress(decided=2, total=4)

    def test_nothing_is_zero(self) -> None:
        assert progress([]) == DecisionProgress(decided=0, total=0)

    @pytest.mark.parametrize(
        ("decided", "total", "expected"),
        [
            (0, 0, ReviewReach.ALL),
            (2, 2, ReviewReach.ALL),
            (0, 2, ReviewReach.NONE),
            (1, 2, ReviewReach.SOME),
        ],
    )
    def test_reach(self, decided: int, total: int, expected: ReviewReach) -> None:
        assert reach(DecisionProgress(decided=decided, total=total)) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("stored", "decided", "learns"),
    [
        (WordStatus.NEW, False, False),
        (WordStatus.LEARN, True, True),
        (WordStatus.LEARNING, True, True),
        (WordStatus.KNOWN, True, False),
    ],
)
def test_the_stored_decision_status_reads_as_the_word_predicates(
    stored: WordStatus, decided: bool, learns: bool,
) -> None:
    assert (stored_decided(stored), stored_chosen_to_learn(stored)) == (decided, learns)
    assert card_is_done(stored, skipped=False, elsewhere=None) is decided


@pytest.mark.unit
class TestSiblingNoteFollowsTheShownStatus:
    """A sibling of a card in Anki says what the user sees: Learned until the 30 days pass,
    Known from day 30 (its timer, not a stored decision)."""

    @pytest.mark.parametrize(("since", "note"), [
        pytest.param(DUE + timedelta(seconds=1), CardNote.LEARNED_ON_OTHER_CARD, id="day-29"),
        pytest.param(DUE, CardNote.KNOWN_ON_OTHER_CARD, id="day-30"),
    ])
    def test_a_sibling_of_a_learning_card(self, since: datetime, note: CardNote) -> None:
        exported = CardState(SIBLING, L, Binding(NoteKind.LEARN, since))
        state = State(_word(_card(N), exported))

        assert state.view().note is note
