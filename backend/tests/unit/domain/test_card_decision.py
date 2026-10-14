"""Decisions on a word through its phrases: what an action does, which buttons work."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    AlreadyInAnkiError,
    CardDecisionLockedError,
    DecidedElsewhereError,
)
from backend.domain.services.card_decision import (
    DecisionAction,
    DecisionButton,
    DecisionOutcome,
    Elsewhere,
    card_state,
    decide,
    wants_generation,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.phrase_origin_kind import DecisionKind, ShownBy
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import make_occurrence, phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence

pytestmark = pytest.mark.unit

LEARN, CLOZE, KNOWN = DecisionAction.LEARN, DecisionAction.CLOZE, DecisionAction.KNOWN
SKIP, UNSKIP, PENDING = DecisionAction.SKIP, DecisionAction.UNSKIP, DecisionAction.PENDING


def _phrase(**changes: object) -> Occurrence:
    return replace(make_occurrence(shown_by=ShownBy.SELECTION), id=7, **changes)  # type: ignore[arg-type]


def _decision(kind: DecisionKind | None = DecisionKind.LEARN, **changes: object) -> Occurrence:
    return _phrase(is_decision=True, decision_kind=kind, **changes)


def _word(status: CandidateStatus) -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=1, lemma="glare", pos="VERB", cefr_level="B2", zipf_frequency=3.0,
        source_phrase=phrase("He glared at me.", "glared"), occurrences=2, status=status,
    )


# ── decide: an undecided word ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("action", "status", "kind"),
    [
        (LEARN, WordStatus.LEARN, DecisionKind.LEARN),
        (CLOZE, WordStatus.LEARN, DecisionKind.CLOZE),
        (KNOWN, WordStatus.KNOWN, None),
    ],
)
def test_a_decision_on_any_phrase_decides_the_word_there(
    action: DecisionAction, status: WordStatus, kind: DecisionKind | None,
) -> None:
    outcome = decide(_phrase(), WordStatus.PENDING, action, None)

    assert outcome == DecisionOutcome(
        word_status=status, is_decision=True, decision_kind=kind, skipped=False,
        drop_cloze=action is not CLOZE,
    )


def test_learn_on_a_skipped_phrase_unskips_it() -> None:
    outcome = decide(_phrase(skipped=True), WordStatus.PENDING, LEARN, None)

    assert outcome.skipped is False
    assert outcome.is_decision


def test_skip_applies_to_the_phrase_only() -> None:
    outcome = decide(_phrase(), WordStatus.PENDING, SKIP, None)

    assert outcome.word_status is WordStatus.PENDING
    assert outcome.skipped is True
    assert outcome.is_decision is False


def test_pending_on_a_skipped_phrase_of_an_undecided_word_unskips_it() -> None:
    outcome = decide(_phrase(skipped=True), WordStatus.PENDING, PENDING, None)

    assert outcome.skipped is False
    assert outcome.word_status is WordStatus.PENDING


@pytest.mark.parametrize("elsewhere", [Elsewhere.KNOWN, Elsewhere.LEARNING])
@pytest.mark.parametrize("action", [LEARN, CLOZE])
def test_learn_on_a_word_known_or_learning_elsewhere_is_refused(
    action: DecisionAction, elsewhere: Elsewhere,
) -> None:
    with pytest.raises(DecidedElsewhereError) as refused:
        decide(_phrase(), WordStatus.PENDING, action, elsewhere)

    assert refused.value.elsewhere is elsewhere


def test_known_on_a_word_known_elsewhere_is_allowed() -> None:
    outcome = decide(_phrase(), WordStatus.PENDING, KNOWN, Elsewhere.KNOWN)

    assert outcome.word_status is WordStatus.KNOWN


# ── decide: a sibling of a decided word ───────────────────────────────


@pytest.mark.parametrize("action", [LEARN, CLOZE, KNOWN, SKIP, PENDING])
@pytest.mark.parametrize("status", [WordStatus.LEARN, WordStatus.KNOWN])
def test_a_sibling_of_a_decided_word_is_locked(
    action: DecisionAction, status: WordStatus,
) -> None:
    with pytest.raises(CardDecisionLockedError):
        decide(_phrase(), status, action, None)


def test_a_skipped_sibling_of_a_decided_word_may_be_unskipped() -> None:
    for action in (UNSKIP, PENDING):
        outcome = decide(_phrase(skipped=True), WordStatus.LEARN, action, None)

        assert outcome == DecisionOutcome(
            word_status=WordStatus.LEARN, is_decision=False, decision_kind=None,
            skipped=False, drop_cloze=False,
        )


def test_unskip_is_allowed_always() -> None:
    assert decide(_phrase(), WordStatus.KNOWN, UNSKIP, None).skipped is False
    assert decide(_phrase(skipped=True), WordStatus.PENDING, UNSKIP, None).skipped is False


# ── decide: the decision phrase ───────────────────────────────────────


def test_undo_on_the_decision_phrase_returns_the_word_to_pending() -> None:
    outcome = decide(_decision(), WordStatus.LEARN, PENDING, None)

    assert outcome == DecisionOutcome(
        word_status=WordStatus.PENDING, is_decision=False, decision_kind=None,
        skipped=False, drop_cloze=True,
    )


def test_known_is_undone_on_the_decision_phrase() -> None:
    outcome = decide(_decision(kind=None), WordStatus.KNOWN, PENDING, None)

    assert outcome.word_status is WordStatus.PENDING


def test_skip_on_the_decision_phrase_undoes_and_skips() -> None:
    outcome = decide(_decision(), WordStatus.LEARN, SKIP, None)

    assert outcome == DecisionOutcome(
        word_status=WordStatus.PENDING, is_decision=False, decision_kind=None,
        skipped=True, drop_cloze=True,
    )


def test_the_decision_changes_on_its_phrase() -> None:
    known = decide(_decision(), WordStatus.LEARN, KNOWN, None)
    plain = decide(_decision(kind=DecisionKind.CLOZE), WordStatus.LEARN, LEARN, None)

    assert known.word_status is WordStatus.KNOWN
    assert known.is_decision
    assert plain.decision_kind is DecisionKind.LEARN
    assert plain.drop_cloze


@pytest.mark.parametrize("action", [PENDING, SKIP])
def test_an_exported_decision_cannot_be_undone(action: DecisionAction) -> None:
    with pytest.raises(AlreadyInAnkiError):
        decide(_decision(exported=True), WordStatus.LEARN, action, None)


def test_an_exported_learn_card_cannot_become_a_cloze() -> None:
    with pytest.raises(AlreadyInAnkiError):
        decide(_decision(exported=True), WordStatus.LEARN, CLOZE, None)


def test_an_exported_cloze_stays_a_cloze_and_keeps_its_markup() -> None:
    known = decide(
        _decision(kind=DecisionKind.CLOZE, exported=True), WordStatus.LEARN, KNOWN, None,
    )
    learn = decide(
        _decision(kind=DecisionKind.CLOZE, exported=True), WordStatus.KNOWN, LEARN, None,
    )

    assert known.decision_kind is DecisionKind.CLOZE
    assert learn.decision_kind is DecisionKind.CLOZE
    assert not known.drop_cloze
    assert not learn.drop_cloze


# ── card state ────────────────────────────────────────────────────────


def test_an_open_card_offers_every_decision() -> None:
    state = card_state(_phrase(), _word(CandidateStatus.PENDING), None)

    assert not state.decided_here
    assert state.decided_elsewhere is None
    assert state.elsewhere is None
    assert state.buttons_enabled == {
        DecisionButton.LEARN, DecisionButton.CLOZE, DecisionButton.KNOWN, DecisionButton.SKIP,
    }


def test_a_skipped_card_can_be_unskipped_or_decided() -> None:
    state = card_state(_phrase(skipped=True), _word(CandidateStatus.SKIP), None)

    assert DecisionButton.UNSKIP in state.buttons_enabled
    assert DecisionButton.LEARN in state.buttons_enabled


def test_the_decision_card_can_be_undone_and_changed() -> None:
    state = card_state(_decision(), _word(CandidateStatus.LEARN), None)

    assert state.decided_here
    assert state.decided_elsewhere is None
    assert state.buttons_enabled == {
        DecisionButton.LEARN, DecisionButton.CLOZE, DecisionButton.KNOWN, DecisionButton.SKIP,
        DecisionButton.UNDO,
    }


def test_an_exported_decision_card_only_switches_learn_and_known() -> None:
    state = card_state(_decision(exported=True), _word(CandidateStatus.LEARN), None)

    assert state.buttons_enabled == {DecisionButton.LEARN, DecisionButton.KNOWN}


def test_a_sibling_card_shows_the_decision_with_its_buttons_inactive() -> None:
    state = card_state(_phrase(), _word(CandidateStatus.KNOWN), None)

    assert not state.decided_here
    assert state.decided_elsewhere is WordStatus.KNOWN
    assert state.buttons_enabled == frozenset()


def test_a_skipped_sibling_shows_the_decision_and_may_be_unskipped() -> None:
    state = card_state(_phrase(skipped=True), _word(CandidateStatus.LEARN), None)

    assert state.decided_elsewhere is WordStatus.LEARN
    assert state.buttons_enabled == {DecisionButton.UNSKIP}


@pytest.mark.parametrize("elsewhere", [Elsewhere.KNOWN, Elsewhere.LEARNING])
def test_a_card_known_elsewhere_is_done_and_cannot_be_learned(elsewhere: Elsewhere) -> None:
    state = card_state(_phrase(), _word(CandidateStatus.PENDING), elsewhere)

    assert state.elsewhere is elsewhere
    assert DecisionButton.LEARN not in state.buttons_enabled
    assert DecisionButton.CLOZE not in state.buttons_enabled
    assert DecisionButton.KNOWN in state.buttons_enabled


def test_a_decided_word_is_not_known_elsewhere() -> None:
    state = card_state(_decision(), _word(CandidateStatus.LEARN), Elsewhere.LEARNING)

    assert state.elsewhere is None


# ── wants_generation: the cards ✨ works on ───────────────────────────


def test_an_open_card_of_a_pending_word_wants_generation() -> None:
    assert wants_generation(_phrase(), _word(CandidateStatus.PENDING), None)


@pytest.mark.parametrize("kind", [DecisionKind.LEARN, DecisionKind.CLOZE])
def test_the_learn_decision_card_wants_generation(kind: DecisionKind) -> None:
    assert wants_generation(_decision(kind), _word(CandidateStatus.LEARN), None)


@pytest.mark.parametrize("status", [CandidateStatus.LEARN, CandidateStatus.KNOWN])
def test_a_sibling_of_a_decided_word_wants_none(status: CandidateStatus) -> None:
    assert not wants_generation(_phrase(), _word(status), None)


def test_the_known_decision_card_wants_none() -> None:
    assert not wants_generation(_decision(None), _word(CandidateStatus.KNOWN), None)


@pytest.mark.parametrize("elsewhere", [Elsewhere.KNOWN, Elsewhere.LEARNING])
def test_a_card_decided_elsewhere_wants_none(elsewhere: Elsewhere) -> None:
    assert not wants_generation(_phrase(), _word(CandidateStatus.PENDING), elsewhere)


def test_a_skipped_card_wants_none() -> None:
    assert not wants_generation(_phrase(skipped=True), _word(CandidateStatus.PENDING), None)


# ── card_state: what each button sends ────────────────────────────────


def _buttons(occ: Occurrence, word: StoredCandidate) -> dict[DecisionButton, tuple[object, bool]]:
    return {b.button: (b.action, b.pressed) for b in card_state(occ, word, None).buttons}


def test_an_open_card_sends_each_decision_and_shows_none_pressed() -> None:
    assert _buttons(_phrase(), _word(CandidateStatus.PENDING)) == {
        DecisionButton.LEARN: (LEARN, False),
        DecisionButton.CLOZE: (CLOZE, False),
        DecisionButton.KNOWN: (KNOWN, False),
        DecisionButton.SKIP: (SKIP, False),
    }


def test_the_pressed_button_of_the_decision_card_undoes_it() -> None:
    buttons = _buttons(_decision(), _word(CandidateStatus.LEARN))
    assert buttons[DecisionButton.LEARN] == (PENDING, True)
    assert buttons[DecisionButton.KNOWN] == (KNOWN, False)
    assert buttons[DecisionButton.SKIP] == (SKIP, False)


def test_the_skipped_sibling_of_a_decided_word_unskips_and_nothing_else() -> None:
    buttons = _buttons(_phrase(skipped=True), _word(CandidateStatus.LEARN))
    assert buttons == {
        DecisionButton.LEARN: (None, True),
        DecisionButton.CLOZE: (None, False),
        DecisionButton.KNOWN: (None, False),
        DecisionButton.SKIP: (UNSKIP, False),
    }


def test_learn_on_a_cloze_card_makes_it_a_plain_card() -> None:
    cloze = _decision(DecisionKind.CLOZE, cloze=_cloze())
    buttons = _buttons(cloze, _word(CandidateStatus.LEARN))
    assert buttons[DecisionButton.LEARN] == (LEARN, False)
    assert buttons[DecisionButton.CLOZE] == (CLOZE, True)


def test_skip_on_a_skipped_open_card_unskips_it_and_shows_pressed() -> None:
    buttons = _buttons(_phrase(skipped=True), _word(CandidateStatus.PENDING))
    assert buttons[DecisionButton.SKIP] == (UNSKIP, True)


def test_a_phrase_in_anki_keeps_its_note_type() -> None:
    exported = _decision(exported=True)
    buttons = _buttons(exported, _word(CandidateStatus.LEARN))
    assert buttons[DecisionButton.LEARN] == (None, True)
    assert buttons[DecisionButton.CLOZE] == (None, False)


def _cloze() -> CandidateCloze:
    from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
    return CandidateCloze(1, (1,), ClozeHintKind.NONE, None, "He glared at me.")
